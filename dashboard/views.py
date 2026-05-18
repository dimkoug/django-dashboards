import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .filters import TodoFilter
from .models import (
    Activity,
    Attachment,
    CalendarFeed,
    Column,
    Comment,
    DashBoard,
    Label,
    Notification,
    SavedView,
    Subtask,
    Todo,
    Webhook,
)
from .permissions import (
    AttachmentPermission,
    CommentPermission,
    DashBoardPermission,
)
from .serializers import (
    ActivitySerializer,
    AttachmentSerializer,
    ChangePasswordSerializer,
    ColumnSerializer,
    CommentSerializer,
    DashBoardSerializer,
    LabelSerializer,
    MeSerializer,
    NotificationSerializer,
    RegisterSerializer,
    SavedViewSerializer,
    SubtaskSerializer,
    TodoSerializer,
    UserSerializer,
    WebhookSerializer,
    can_access_dashboard,
    notify_attachment,
    notify_comment,
    notify_mentioned,
    record_activity,
    resolve_mentioned_users,
    spawn_next_occurrence,
)
from .ws_tickets import issue_ticket

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Open self-registration. Overrides the global IsAuthenticated."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class UserListView(generics.ListAPIView):
    """User lookup for pickers. Requires ?search= (>=2 chars) so the
    full user list can't be enumerated; matches username icontains."""
    serializer_class = UserSerializer

    def get_queryset(self):
        term = (self.request.query_params.get('search') or '').strip()
        if len(term) < 2:
            return User.objects.none()
        return (User.objects
                .filter(username__icontains=term)
                .order_by('username')
                .only('id', 'username'))


class MeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the current user's profile (username read-only)."""
    serializer_class = MeSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'status': 'password changed'})


class LogoutView(APIView):
    """Blacklist the supplied refresh token (real logout)."""
    def post(self, request):
        token = request.data.get('refresh')
        if not token:
            return Response({'refresh': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            return Response({'refresh': 'Invalid or expired token.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class DashBoardViewSet(viewsets.ModelViewSet):
    """Dashboards owned by, or shared with, the authenticated user.
    Only the owner may modify/delete/share (see DashBoardPermission)."""
    serializer_class = DashBoardSerializer
    permission_classes = [IsAuthenticated, DashBoardPermission]

    def get_queryset(self):
        u = self.request.user
        return (
            DashBoard.objects
            .filter(Q(user=u) | Q(users=u))
            .prefetch_related('users')
            .order_by('-created_at')
            .distinct()
        )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Aggregate metrics for the dashboard (access-checked)."""
        dashboard = self.get_object()
        todos = Todo.objects.filter(column__dashboard=dashboard)
        now = timezone.now()

        total = todos.count()
        completed = todos.filter(completed=True).count()
        overdue = todos.filter(
            completed=False, end_date__lt=now).count()

        priority = {p: 0 for p in ('low', 'medium', 'high')}
        for row in todos.values('priority').annotate(c=Count('id')):
            priority[row['priority']] = row['c']

        by_column = list(
            Column.objects.filter(dashboard=dashboard)
            .values('id', 'name')
            .annotate(
                total=Count('todos', distinct=True),
                completed=Count('todos', filter=Q(todos__completed=True),
                                distinct=True))
            .order_by('name'))

        by_assignee = list(
            todos.exclude(users__isnull=True)
            .values('users__username')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count'))

        return Response({
            'total': total,
            'open': total - completed,
            'completed': completed,
            'overdue': overdue,
            'by_priority': priority,
            'by_column': by_column,
            'by_assignee': [
                {'username': r['users__username'], 'count': r['count']}
                for r in by_assignee
            ],
        })


class ColumnViewSet(viewsets.ModelViewSet):
    """Columns in dashboards the user owns or is a member of."""
    serializer_class = ColumnSerializer

    def get_queryset(self):
        u = self.request.user
        return (
            Column.objects
            .filter(Q(dashboard__user=u) | Q(dashboard__users=u))
            .select_related('dashboard')
            .order_by('-created_at')
            .distinct()
        )


class TodoViewSet(viewsets.ModelViewSet):
    """Todos in dashboards the user owns or is a member of.

    Filtering: ?completed= ?assignee= ?search=<name> ?ordering=<field>
    """
    serializer_class = TodoSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TodoFilter
    search_fields = ['name']
    ordering_fields = ['end_date', 'start_date', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        u = self.request.user
        return (
            Todo.objects
            .filter(Q(column__dashboard__user=u)
                    | Q(column__dashboard__users=u))
            .select_related('column', 'column__dashboard')
            .prefetch_related('users', 'labels', 'subtasks', 'blockers')
            .order_by('-created_at')
            .distinct()
        )

    @action(detail=False, methods=['get'])
    def assigned(self, request):
        """Todos the current user is assigned to (any dashboard)."""
        qs = (
            Todo.objects
            .filter(users=request.user)
            .select_related('column', 'column__dashboard')
            .prefetch_related('users', 'labels', 'subtasks', 'blockers')
            .order_by('-created_at')
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist card order within a column.

        Body: {"column": <id>, "order": [todoId, ...]}
        Every id must be a todo currently in that column.
        """
        column_id = request.data.get('column')
        order = request.data.get('order') or []
        try:
            column = Column.objects.select_related('dashboard').get(
                pk=column_id)
        except Column.DoesNotExist:
            return Response({'column': 'Not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not can_access_dashboard(column.dashboard, request.user):
            return Response({'column': 'Not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        ids = [int(i) for i in order]
        existing = set(
            Todo.objects.filter(column=column).values_list('id', flat=True))
        if len(ids) != len(set(ids)) or set(ids) != existing:
            return Response(
                {'order': 'Must list exactly the todos in this column.'},
                status=status.HTTP_400_BAD_REQUEST)
        todos = list(Todo.objects.filter(id__in=ids))

        rank = {tid: i for i, tid in enumerate(ids)}
        for t in todos:
            t.position = rank[t.id]
        Todo.objects.bulk_update(todos, ['position'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """Apply one action to many todos.

        Body: {"ids":[...], "action": <a>, "value": <v>}
        action in: complete | reopen | move | label_add | delete
          move      -> value = target column id (must be same dashboard)
          label_add -> value = label id (must be same dashboard)
        """
        ids = request.data.get('ids') or []
        act = request.data.get('action')
        value = request.data.get('value')
        valid = {'complete', 'reopen', 'move', 'label_add', 'delete'}
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            ids = []
        if not ids or act not in valid:
            return Response({'detail': 'ids and a valid action required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        u = request.user
        qs = (Todo.objects
              .filter(id__in=ids)
              .filter(Q(column__dashboard__user=u)
                      | Q(column__dashboard__users=u))
              .select_related('column', 'column__dashboard')
              .distinct())
        todos = list(qs)
        if len(todos) != len(set(ids)):
            return Response({'ids': 'Some todos were not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            if act == 'delete':
                n = len(todos)
                qs.delete()
                result = {'deleted': n}
            elif act == 'reopen':
                qs.update(completed=False)
                result = {'updated': len(todos)}
            elif act == 'complete':
                newly = [t for t in todos if not t.completed]
                Todo.objects.filter(
                    id__in=[t.id for t in newly]).update(completed=True)
                for t in newly:
                    if t.recurrence != Todo.Recurrence.NONE:
                        spawn_next_occurrence(t)
                result = {'updated': len(newly)}
            elif act == 'move':
                try:
                    target = Column.objects.select_related(
                        'dashboard').get(pk=value)
                except (Column.DoesNotExist, ValueError, TypeError):
                    return Response({'value': 'Column not found.'},
                                    status=status.HTTP_404_NOT_FOUND)
                if not can_access_dashboard(target.dashboard, u):
                    return Response({'value': 'Column not found.'},
                                    status=status.HTTP_404_NOT_FOUND)
                if any(t.column.dashboard_id != target.dashboard_id
                       for t in todos):
                    return Response(
                        {'value': 'All todos must be in the target '
                                  "column's dashboard."},
                        status=status.HTTP_400_BAD_REQUEST)
                qs.update(column=target)
                result = {'updated': len(todos)}
            else:  # label_add
                try:
                    label = Label.objects.select_related(
                        'dashboard').get(pk=value)
                except (Label.DoesNotExist, ValueError, TypeError):
                    return Response({'value': 'Label not found.'},
                                    status=status.HTTP_404_NOT_FOUND)
                if not can_access_dashboard(label.dashboard, u):
                    return Response({'value': 'Label not found.'},
                                    status=status.HTTP_404_NOT_FOUND)
                if any(t.column.dashboard_id != label.dashboard_id
                       for t in todos):
                    return Response(
                        {'value': "Label must be in the todos' dashboard."},
                        status=status.HTTP_400_BAD_REQUEST)
                for t in todos:
                    t.labels.add(label)
                result = {'updated': len(todos)}

            for dash in DashBoard.objects.filter(
                    id__in={t.column.dashboard_id for t in todos}):
                record_activity(dash, u, 'bulk',
                                f'bulk {act} {len(todos)} todo(s)')

        return Response(result)


class LabelViewSet(viewsets.ModelViewSet):
    """Labels in dashboards the user owns or is a member of."""
    serializer_class = LabelSerializer

    def get_queryset(self):
        u = self.request.user
        return (
            Label.objects
            .filter(Q(dashboard__user=u) | Q(dashboard__users=u))
            .select_related('dashboard')
            .order_by('name')
            .distinct()
        )


class CommentViewSet(viewsets.ModelViewSet):
    """Comments on todos in accessible dashboards. ?todo=<id> to filter.
    Create/read for any member; delete only by author or dashboard owner."""
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, CommentPermission]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        u = self.request.user
        qs = (
            Comment.objects
            .filter(Q(todo__column__dashboard__user=u)
                    | Q(todo__column__dashboard__users=u))
            .select_related('author', 'todo', 'todo__column',
                            'todo__column__dashboard')
            .distinct()
        )
        todo_id = self.request.query_params.get('todo')
        if todo_id:
            qs = qs.filter(todo_id=todo_id)
        return qs

    def perform_create(self, serializer):
        comment = serializer.save()
        todo = comment.todo
        record_activity(
            todo.column.dashboard, self.request.user, 'commented',
            f'commented on "{todo.name}"')
        mentioned = list(resolve_mentioned_users(comment))
        notify_mentioned(comment, mentioned)
        # Mentioned users get the specific 'mentioned' toast instead of
        # the generic 'comment_added' one.
        notify_comment(todo, self.request.user,
                       exclude_ids=[u.id for u in mentioned])


class AttachmentViewSet(viewsets.ModelViewSet):
    """File attachments on todos in accessible dashboards. ?todo=<id>.
    Members upload/read; delete only by uploader or dashboard owner."""
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated, AttachmentPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        u = self.request.user
        qs = (
            Attachment.objects
            .filter(Q(todo__column__dashboard__user=u)
                    | Q(todo__column__dashboard__users=u))
            .select_related('uploaded_by', 'todo', 'todo__column',
                            'todo__column__dashboard')
            .distinct()
        )
        todo_id = self.request.query_params.get('todo')
        if todo_id:
            qs = qs.filter(todo_id=todo_id)
        return qs

    def perform_create(self, serializer):
        attachment = serializer.save(uploaded_by=self.request.user)
        todo = attachment.todo
        record_activity(
            todo.column.dashboard, self.request.user, 'attached',
            f'attached "{attachment.original_name}" to "{todo.name}"')
        notify_attachment(todo, self.request.user)

    def perform_destroy(self, instance):
        # Remove the file from storage, then the row.
        instance.file.delete(save=False)
        instance.delete()


class ActivityListView(generics.ListAPIView):
    """Read-only activity feed. ?dashboard=<id> (required-ish)."""
    serializer_class = ActivitySerializer

    def get_queryset(self):
        u = self.request.user
        qs = (
            Activity.objects
            .filter(Q(dashboard__user=u) | Q(dashboard__users=u))
            .select_related('actor', 'dashboard')
            .distinct()
        )
        dash = self.request.query_params.get('dashboard')
        if dash:
            qs = qs.filter(dashboard_id=dash)
        return qs


class GlobalSearchView(APIView):
    """?q= search over todos (name/description) and comments (body)
    across dashboards the user can access. Requires q (>=2 chars)."""

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'todos': [], 'comments': []})
        u = request.user

        todos = (
            Todo.objects
            .filter(Q(column__dashboard__user=u)
                    | Q(column__dashboard__users=u))
            .filter(Q(name__icontains=q) | Q(description__icontains=q))
            .select_related('column', 'column__dashboard')
            .distinct()[:50]
        )
        comments = (
            Comment.objects
            .filter(Q(todo__column__dashboard__user=u)
                    | Q(todo__column__dashboard__users=u))
            .filter(body__icontains=q)
            .select_related('author', 'todo', 'todo__column',
                            'todo__column__dashboard')
            .distinct()[:50]
        )
        return Response({
            'todos': [
                {
                    'id': t.id,
                    'name': t.name,
                    'column': t.column_id,
                    'dashboard_id': t.column.dashboard_id,
                    'dashboard_name': t.column.dashboard.name,
                }
                for t in todos
            ],
            'comments': [
                {
                    'id': c.id,
                    'body': c.body,
                    'author': c.author.username if c.author else None,
                    'todo': c.todo_id,
                    'todo_name': c.todo.name,
                    'dashboard_id': c.todo.column.dashboard_id,
                    'column': c.todo.column_id,
                }
                for c in comments
            ],
        })


class SavedViewViewSet(viewsets.ModelViewSet):
    """Per-user saved filter presets (private to the owner)."""
    serializer_class = SavedViewSerializer

    def get_queryset(self):
        return SavedView.objects.filter(user=self.request.user)


class SubtaskViewSet(viewsets.ModelViewSet):
    """Checklist items on todos in accessible dashboards. ?todo=<id>.
    Any member may add/toggle/delete (collaboration)."""
    serializer_class = SubtaskSerializer

    def get_queryset(self):
        u = self.request.user
        qs = (
            Subtask.objects
            .filter(Q(todo__column__dashboard__user=u)
                    | Q(todo__column__dashboard__users=u))
            .select_related('todo', 'todo__column',
                            'todo__column__dashboard')
            .distinct()
        )
        todo_id = self.request.query_params.get('todo')
        if todo_id:
            qs = qs.filter(todo_id=todo_id)
        return qs


def _ics_escape(text):
    return (str(text or '')
            .replace('\\', '\\\\')
            .replace(';', '\\;')
            .replace(',', '\\,')
            .replace('\n', '\\n'))


def _ics_dt(dt):
    return dt.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


class CalendarFeedView(APIView):
    """GET -> current user's iCal feed token/path (created on first
    access). POST -> rotate the token (old URL stops working)."""

    def _feed(self, user):
        feed, _ = CalendarFeed.objects.get_or_create(user=user)
        return feed

    def _payload(self, feed):
        return {'token': feed.token,
                'path': f'/api/calendar/{feed.token}.ics'}

    def get(self, request):
        return Response(self._payload(self._feed(request.user)))

    def post(self, request):
        from .models import _new_calendar_token
        feed = self._feed(request.user)
        feed.token = _new_calendar_token()
        feed.save(update_fields=['token'])
        return Response(self._payload(feed))


class CalendarICSView(APIView):
    """Public (token-authenticated) iCal feed of the user's assigned
    todos. The secret token in the URL is the only credential."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            feed = CalendarFeed.objects.select_related('user').get(
                token=token)
        except CalendarFeed.DoesNotExist:
            return HttpResponse(status=404)

        todos = (
            Todo.objects.filter(users=feed.user)
            .select_related('column', 'column__dashboard')
            .order_by('start_date')
        )
        now = _ics_dt(timezone.now())
        lines = [
            'BEGIN:VCALENDAR', 'VERSION:2.0',
            'PRODID:-//dashboard//todos//EN', 'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH', 'X-WR-CALNAME:My Todos',
        ]
        for t in todos:
            start = t.start_date
            end = t.end_date or (start + datetime.timedelta(hours=1))
            lines += [
                'BEGIN:VEVENT',
                f'UID:todo-{t.id}@dashboard',
                f'DTSTAMP:{now}',
                f'DTSTART:{_ics_dt(start)}',
                f'DTEND:{_ics_dt(end)}',
                f'SUMMARY:{_ics_escape(t.name)}',
                f'DESCRIPTION:{_ics_escape(t.column.dashboard.name)}',
                f'STATUS:{"COMPLETED" if t.completed else "CONFIRMED"}',
                'END:VEVENT',
            ]
        lines.append('END:VCALENDAR')
        body = '\r\n'.join(lines) + '\r\n'
        return HttpResponse(
            body, content_type='text/calendar; charset=utf-8')


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """The current user's notifications + read-state actions."""
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        n = Notification.objects.filter(
            user=request.user, read=False).count()
        return Response({'count': n})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        self.get_queryset().filter(pk=pk).update(read=True)
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def read_all(self, request):
        self.get_queryset().filter(read=False).update(read=True)
        return Response({'status': 'ok'})


class WebhookViewSet(viewsets.ModelViewSet):
    """Outbound webhooks, managed by the dashboard owner only."""
    serializer_class = WebhookSerializer

    def get_queryset(self):
        return Webhook.objects.filter(dashboard__user=self.request.user)


class WSTicketView(APIView):
    """Mint a short-lived single-use ticket for the WebSocket handshake
    (so no long-lived JWT is ever placed in a WS URL)."""

    def post(self, request):
        return Response({'ticket': issue_ticket(request.user.id)})
