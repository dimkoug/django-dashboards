import calendar
import json
import logging
import re
import urllib.request
from datetime import timedelta

import markdown as md
import nh3
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import serializers

from .consumers import group_for
from .models import (
    Activity,
    Attachment,
    Column,
    Comment,
    DashBoard,
    Label,
    Notification,
    SavedView,
    Subtask,
    Todo,
    UserPreference,
    Webhook,
)

WEBHOOK_EVENTS = ('created', 'completed', 'moved')

User = get_user_model()
logger = logging.getLogger(__name__)


def record_activity(dashboard, actor, verb, message):
    """Append a dashboard activity-feed entry. Best-effort."""
    try:
        Activity.objects.create(
            dashboard=dashboard, actor=actor, verb=verb,
            message=message[:255])
    except Exception:  # noqa: BLE001 - activity log is non-critical
        logger.exception('Failed to record activity: %s', verb)


def dashboard_member_ids(dashboard, exclude=None):
    """Owner + shared members of a dashboard (optionally excluding one id)."""
    ids = {dashboard.user_id, *dashboard.users.values_list('id', flat=True)}
    ids.discard(exclude)
    return ids


def can_access_dashboard(dashboard, user):
    """Owner or a shared member may view/collaborate on a dashboard."""
    return (dashboard.user_id == user.id
            or dashboard.users.filter(id=user.id).exists())


def _add_months(dt, months):
    m = dt.month - 1 + months
    year = dt.year + m // 12
    month = m % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _shift(dt, recurrence):
    if dt is None:
        return None
    if recurrence == 'daily':
        return dt + timedelta(days=1)
    if recurrence == 'weekly':
        return dt + timedelta(days=7)
    if recurrence == 'monthly':
        return _add_months(dt, 1)
    return dt


def spawn_next_occurrence(todo):
    """Clone a recurring todo as the next, uncompleted occurrence
    (dates shifted; priority/labels/assignees/checklist carried over).
    Returns the new Todo or None."""
    from .models import Subtask, Todo  # local import avoids cycle

    rec = todo.recurrence
    if rec == Todo.Recurrence.NONE:
        return None

    nxt = Todo.objects.create(
        column=todo.column,
        name=todo.name,
        description=todo.description,
        priority=todo.priority,
        recurrence=rec,
        completed=False,
        start_date=_shift(todo.start_date, rec),
        end_date=_shift(todo.end_date, rec),
    )
    nxt.users.set(todo.users.all())
    nxt.labels.set(todo.labels.all())
    # Fresh (unchecked) copy of the checklist template.
    Subtask.objects.bulk_create([
        Subtask(todo=nxt, text=s.text, position=s.position, done=False)
        for s in todo.subtasks.all()
    ])
    return nxt


def _send_event(user_ids, data):
    """Push a real-time event to each given user's notification group.

    Best-effort: a channel-layer/Redis failure must not break the API write.
    """
    user_ids = list(user_ids)
    if not user_ids:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    payload = {'type': 'notify', 'data': data}
    for uid in user_ids:
        try:
            async_to_sync(layer.group_send)(group_for(uid), payload)
        except Exception:  # noqa: BLE001 - notifications are non-critical
            logger.exception('Failed to send notification: %s', data.get('event'))


def _persist(user_ids, kind, text, link=''):
    """Store a Notification row per recipient (best-effort)."""
    from .models import Notification
    rows = [Notification(user_id=uid, kind=kind, text=text, link=link)
            for uid in user_ids]
    if not rows:
        return
    try:
        Notification.objects.bulk_create(rows)
    except Exception:  # noqa: BLE001 - non-critical
        logger.exception('Failed to persist notifications: %s', kind)


def _email_users(user_ids, subject, body, pref_field):
    """Email recipients who have an address and haven't opted out
    (missing preference row = default opted-in). Best-effort."""
    ids = list(user_ids)
    if not ids:
        return
    prefs = {p.user_id: p for p in
             UserPreference.objects.filter(user_id__in=ids)}
    for u in User.objects.filter(id__in=ids).exclude(email=''):
        pref = prefs.get(u.id)
        if pref is not None and not getattr(pref, pref_field):
            continue
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                      [u.email], fail_silently=True)
        except Exception:  # noqa: BLE001 - email is non-critical
            logger.info('Email send failed to %s', u.email)


def _todo_link(todo):
    return (f'/dashboards/{todo.column.dashboard_id}'
            f'/columns/{todo.column_id}')


def notify_assigned(todo, user_ids):
    ids = list(user_ids)
    _persist(ids, 'todo_assigned',
             f'You were assigned to "{todo.name}"', _todo_link(todo))
    _email_users(ids, f'Assigned: {todo.name}',
                 f'You were assigned to the todo "{todo.name}".',
                 'email_on_assign')
    _send_event(ids, {
        'event': 'todo_assigned',
        'todo_id': todo.id,
        'todo_name': todo.name,
    })


def notify_dashboard_shared(dashboard, user_ids):
    ids = list(user_ids)
    _persist(ids, 'dashboard_shared',
             f'"{dashboard.name}" was shared with you', '/dashboards')
    _send_event(ids, {
        'event': 'dashboard_shared',
        'dashboard_id': dashboard.id,
        'dashboard_name': dashboard.name,
    })


MENTION_RE = re.compile(r'@([\w.\-]+)')


def parse_mention_usernames(body):
    """Distinct @usernames referenced in a comment body."""
    return list({m for m in MENTION_RE.findall(body or '')})


def resolve_mentioned_users(comment):
    """Mentioned users who actually have access to the dashboard
    (owner or member) and aren't the comment's author."""
    names = parse_mention_usernames(comment.body)
    if not names:
        return User.objects.none()
    dashboard = comment.todo.column.dashboard
    member_ids = dashboard_member_ids(dashboard, exclude=comment.author_id)
    return User.objects.filter(username__in=names, id__in=member_ids)


def notify_comment(todo, actor, exclude_ids=()):
    """Tell the dashboard's members (except the commenter and any
    explicitly excluded ids, e.g. people who got a mention instead)."""
    dashboard = todo.column.dashboard
    recipients = list(set(dashboard_member_ids(dashboard, exclude=actor.id))
                      - set(exclude_ids))
    _persist(recipients, 'comment_added',
             f'{actor.username} commented on "{todo.name}"',
             _todo_link(todo))
    _send_event(recipients, {
        'event': 'comment_added',
        'todo_id': todo.id,
        'todo_name': todo.name,
        'actor': actor.username,
    })


def notify_mentioned(comment, users):
    """Targeted 'mentioned' event to each mentioned dashboard member."""
    todo = comment.todo
    ids = [u.id for u in users]
    _persist(ids, 'mentioned',
             f'{comment.author.username} mentioned you in "{todo.name}"',
             _todo_link(todo))
    _email_users(ids, f'Mentioned in "{todo.name}"',
                 f'{comment.author.username} mentioned you: '
                 f'{comment.body}', 'email_on_mention')
    _send_event(ids, {
        'event': 'mentioned',
        'todo_id': todo.id,
        'todo_name': todo.name,
        'actor': comment.author.username,
        'comment_id': comment.id,
    })


def notify_attachment(todo, actor):
    """Tell the dashboard's members (except the uploader) about a file."""
    dashboard = todo.column.dashboard
    recipients = list(dashboard_member_ids(dashboard, exclude=actor.id))
    _persist(recipients, 'attachment_added',
             f'{actor.username} attached a file to "{todo.name}"',
             _todo_link(todo))
    _send_event(recipients, {
        'event': 'attachment_added',
        'todo_id': todo.id,
        'todo_name': todo.name,
        'actor': actor.username,
    })


def due_reminder_text(todo, overdue):
    """Notification text for a due reminder. Kept as a single source of
    truth so the notify_due command can dedupe on the exact string."""
    return f'"{todo.name}" is {"overdue" if overdue else "due soon"}'


def notify_due(todo, user_ids, overdue):
    """Remind the given assignees that a todo is overdue / due soon
    (persisted + real-time + email, the last gated by email_on_due)."""
    ids = list(user_ids)
    if not ids:
        return
    kind = 'due_overdue' if overdue else 'due_soon'
    label = 'overdue' if overdue else 'due soon'
    text = due_reminder_text(todo, overdue)
    _persist(ids, kind, text, _todo_link(todo))
    _email_users(ids, f'Reminder: "{todo.name}" is {label}',
                 f'The todo "{todo.name}" is {label}.',
                 'email_on_due')
    _send_event(ids, {
        'event': kind,
        'todo_id': todo.id,
        'todo_name': todo.name,
    })


def _deliver_webhook(url, data):
    try:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode(),
            headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=2).close()
    except Exception:  # noqa: BLE001 - outbound webhook is best-effort
        logger.info('Webhook delivery failed: %s', url)


def fire_webhooks(todo, event):
    """Best-effort outbound POST to a dashboard's active webhooks."""
    dashboard = todo.column.dashboard
    payload = {
        'event': event,
        'todo': {
            'id': todo.id,
            'name': todo.name,
            'column': todo.column_id,
            'dashboard': dashboard.id,
            'completed': todo.completed,
        },
    }
    for wh in dashboard.webhooks.filter(active=True):
        if not wh.events or event in wh.events:
            _deliver_webhook(wh.url, payload)


class UserSerializer(serializers.ModelSerializer):
    """Minimal user info for assignment pickers."""

    class Meta:
        model = User
        fields = ['id', 'username']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(
        write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password2']

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {'password2': "Passwords don't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2', None)
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
        read_only_fields = ['id', 'username']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is wrong.')
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class DashBoardSerializer(serializers.ModelSerializer):
    # Owner is always the authenticated user; never client-supplied.
    # Including it as a HiddenField keeps the (user, name) unique-together
    # validator working so duplicates return 400 instead of a 500.
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    is_owner = serializers.SerializerMethodField()
    # Nested member info so the UI never needs a global user list to display.
    members = UserSerializer(source='users', many=True, read_only=True)

    class Meta:
        model = DashBoard
        fields = ['id', 'user', 'is_owner', 'users', 'members', 'name',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and obj.user_id == request.user.id)

    def update(self, instance, validated_data):
        had_users = 'users' in validated_data
        before = (set(instance.users.values_list('id', flat=True))
                  if had_users else set())
        dashboard = super().update(instance, validated_data)
        if had_users:
            after = set(dashboard.users.values_list('id', flat=True))
            notify_dashboard_shared(dashboard, after - before)
        return dashboard


class ColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Column
        fields = ['id', 'dashboard', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_dashboard(self, value):
        if not can_access_dashboard(value, self.context['request'].user):
            raise serializers.ValidationError('Dashboard not found.')
        return value


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'dashboard', 'name', 'color',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_dashboard(self, value):
        if not can_access_dashboard(value, self.context['request'].user):
            raise serializers.ValidationError('Dashboard not found.')
        return value

    def validate_color(self, value):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value or ''):
            raise serializers.ValidationError(
                'Color must be a hex value like #6366f1.')
        return value


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ['id', 'todo', 'text', 'done', 'position', 'created_at']
        read_only_fields = ['position', 'created_at']

    def validate_todo(self, value):
        if not can_access_dashboard(value.column.dashboard,
                                    self.context['request'].user):
            raise serializers.ValidationError('Todo not found.')
        return value


class TodoSerializer(serializers.ModelSerializer):
    description_html = serializers.SerializerMethodField()
    # Nested assignee info so the UI never needs a global user list.
    assignees = UserSerializer(source='users', many=True, read_only=True)
    subtask_summary = serializers.SerializerMethodField()
    blockers_open = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = ['id', 'column', 'name', 'description', 'description_html',
                  'priority', 'users', 'assignees', 'labels', 'blockers',
                  'blockers_open', 'position', 'subtask_summary',
                  'recurrence', 'start_date', 'end_date', 'completed',
                  'created_at', 'updated_at']
        # position is set on create (appended) and via the reorder action.
        read_only_fields = ['created_at', 'updated_at', 'position']

    def get_blockers_open(self, obj):
        # Uses prefetched blockers (see TodoViewSet) -> no extra query.
        return sum(1 for b in obj.blockers.all() if not b.completed)

    def get_description_html(self, obj):
        # Markdown -> sanitized HTML (nh3) so it's safe to render.
        return nh3.clean(
            md.markdown(obj.description or '',
                        extensions=['fenced_code', 'tables']))

    def get_subtask_summary(self, obj):
        # Uses prefetched subtasks (see TodoViewSet) -> no extra query.
        subs = obj.subtasks.all()
        return {'total': len(subs),
                'done': sum(1 for s in subs if s.done)}

    def validate_column(self, value):
        if not can_access_dashboard(value.dashboard,
                                    self.context['request'].user):
            raise serializers.ValidationError('Column not found.')
        # Moving a todo: the target column must stay in the same dashboard.
        # (On create there is no source column, so this only guards moves.)
        if (self.instance is not None
                and value.dashboard_id != self.instance.column.dashboard_id):
            raise serializers.ValidationError(
                'Cannot move a todo to a column in a different dashboard.')
        return value

    def validate(self, attrs):
        # Resolve effective start/end, falling back to the existing instance
        # for PATCH and to the model default (now) when creating without one.
        start = attrs.get('start_date')
        end = attrs.get('end_date')
        if start is None:
            start = self.instance.start_date if self.instance else timezone.now()
        if end is None and self.instance is not None:
            end = self.instance.end_date

        if end is not None and end <= start:
            raise serializers.ValidationError(
                {'end_date': 'end_date must be after start_date.'})

        column = attrs.get('column') or (
            self.instance.column if self.instance else None)

        # Labels must belong to the same dashboard as the todo's column.
        labels = attrs.get('labels')
        if labels and column is not None and any(
                lbl.dashboard_id != column.dashboard_id for lbl in labels):
            raise serializers.ValidationError(
                {'labels': "Labels must belong to the todo's dashboard."})

        # Blockers: same dashboard, not self.
        blockers = attrs.get('blockers')
        if blockers is not None:
            if self.instance is not None and any(
                    b.id == self.instance.id for b in blockers):
                raise serializers.ValidationError(
                    {'blockers': 'A todo cannot block itself.'})
            if column is not None and any(
                    b.column.dashboard_id != column.dashboard_id
                    for b in blockers):
                raise serializers.ValidationError(
                    {'blockers': 'Blockers must be in the same dashboard.'})

        # Can't complete while any blocker is still open.
        completing = attrs.get('completed') is True
        if completing:
            effective = (blockers if blockers is not None
                         else (list(self.instance.blockers.all())
                               if self.instance else []))
            if any(not b.completed for b in effective):
                raise serializers.ValidationError(
                    {'completed': 'Resolve open blockers first.'})
        return attrs

    def create(self, validated_data):
        # Todo.save() handles position append (works for every create path).
        todo = super().create(validated_data)
        notify_assigned(todo, todo.users.values_list('id', flat=True))
        actor = self.context['request'].user
        record_activity(todo.column.dashboard, actor, 'created_todo',
                         f'created todo "{todo.name}"')
        fire_webhooks(todo, 'created')
        return todo

    def update(self, instance, validated_data):
        before_users = set(instance.users.values_list('id', flat=True))
        was_completed = instance.completed
        old_column_id = instance.column_id
        todo = super().update(instance, validated_data)
        actor = self.context['request'].user
        dashboard = todo.column.dashboard

        if 'users' in validated_data:
            after = set(todo.users.values_list('id', flat=True))
            notify_assigned(todo, after - before_users)
        if 'completed' in validated_data and todo.completed != was_completed:
            verb = 'completed_todo' if todo.completed else 'reopened_todo'
            record_activity(dashboard, actor, verb,
                            f'{verb.split("_")[0]} "{todo.name}"')
            if todo.completed:
                fire_webhooks(todo, 'completed')
            # Completing a recurring todo spawns the next occurrence.
            if todo.completed and todo.recurrence != Todo.Recurrence.NONE:
                nxt = spawn_next_occurrence(todo)
                if nxt is not None:
                    record_activity(dashboard, actor, 'recurred',
                                    f'recurred "{todo.name}"')
                    notify_assigned(
                        nxt, nxt.users.values_list('id', flat=True))
        if 'column' in validated_data and todo.column_id != old_column_id:
            record_activity(dashboard, actor, 'moved_todo',
                            f'moved "{todo.name}" to {todo.column.name}')
            fire_webhooks(todo, 'moved')
        return todo


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())
    author_username = serializers.CharField(
        source='author.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'todo', 'author', 'author_username', 'body',
                  'created_at']
        read_only_fields = ['created_at']

    def validate_todo(self, value):
        if not can_access_dashboard(value.column.dashboard,
                                    self.context['request'].user):
            raise serializers.ValidationError('Todo not found.')
        return value


class ActivitySerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source='actor.username', read_only=True, default=None)

    class Meta:
        model = Activity
        fields = ['id', 'dashboard', 'actor_username', 'verb', 'message',
                  'created_at']
        read_only_fields = fields


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(
        source='uploaded_by.username', read_only=True, default=None)
    size = serializers.SerializerMethodField()
    # Origin-relative URL (/media/...) so it works behind the nginx proxy
    # regardless of host/port; an absolute URL would drop the :9005 port.
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ['id', 'todo', 'file', 'file_url', 'original_name',
                  'uploaded_by_username', 'size', 'created_at']
        read_only_fields = ['original_name', 'created_at']

    def get_file_url(self, obj):
        try:
            return obj.file.url
        except ValueError:
            return None

    def get_size(self, obj):
        try:
            return obj.file.size
        except (ValueError, OSError):
            return None

    def validate_todo(self, value):
        if not can_access_dashboard(value.column.dashboard,
                                    self.context['request'].user):
            raise serializers.ValidationError('Todo not found.')
        return value

    def create(self, validated_data):
        uploaded = validated_data['file']
        validated_data['original_name'] = getattr(
            uploaded, 'name', 'file')[:255]
        return super().create(validated_data)


class SavedViewSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = SavedView
        fields = ['id', 'user', 'name', 'params', 'created_at']
        read_only_fields = ['created_at']

    def validate_params(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('params must be an object.')
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'kind', 'text', 'link', 'read', 'created_at']
        read_only_fields = fields


class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = ['id', 'dashboard', 'url', 'events', 'active',
                  'created_at']
        read_only_fields = ['created_at']

    def validate_dashboard(self, value):
        # Only the dashboard OWNER may manage its webhooks.
        if value.user_id != self.context['request'].user.id:
            raise serializers.ValidationError('Dashboard not found.')
        return value

    def validate_events(self, value):
        if not isinstance(value, list) or any(
                e not in WEBHOOK_EVENTS for e in value):
            raise serializers.ValidationError(
                f'events must be a list from {list(WEBHOOK_EVENTS)} '
                f'(empty = all).')
        return value


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['email_on_assign', 'email_on_mention', 'email_on_due',
                  'theme']
