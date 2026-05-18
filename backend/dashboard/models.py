from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
User = get_user_model()



# Create your models here.
class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class DashBoard(Timestamped):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owned_dashboards')
    users = models.ManyToManyField(
        User, blank=True, related_name='shared_dashboards')
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name



class Column(Timestamped):
    dashboard = models.ForeignKey(DashBoard, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    class Meta:
        default_related_name = 'columns'
        unique_together = ('dashboard', 'name')

    def __str__(self):
        return self.name
    

class Label(Timestamped):
    dashboard = models.ForeignKey(DashBoard, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        default_related_name = 'labels'
        unique_together = ('dashboard', 'name')

    def __str__(self):
        return self.name


class Todo(Timestamped):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class Recurrence(models.TextChoices):
        NONE = 'none', 'None'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    column = models.ForeignKey(Column, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    users = models.ManyToManyField(
        User, blank=True, related_name='assigned_todos')
    labels = models.ManyToManyField(Label, blank=True, related_name='todos')
    blockers = models.ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='blocking')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True,blank=True)
    completed = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    recurrence = models.CharField(
        max_length=10, choices=Recurrence.choices,
        default=Recurrence.NONE)

    class Meta:
        default_related_name = 'todos'
        ordering = ['position', 'id']

    def save(self, *args, **kwargs):
        # New todos append to the end of their column (any create path).
        if self._state.adding and not self.position:
            last = (Todo.objects.filter(column=self.column)
                    .order_by('-position')
                    .values_list('position', flat=True)
                    .first())
            self.position = 0 if last is None else last + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Comment(Timestamped):
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()

    class Meta:
        default_related_name = 'comments'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.author}: {self.body[:30]}'


class Activity(models.Model):
    dashboard = models.ForeignKey(
        DashBoard, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='activities')
    verb = models.CharField(max_length=32)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.actor} {self.verb}'


class Attachment(Timestamped):
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE)
    file = models.FileField(upload_to='attachments/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='attachments')

    class Meta:
        default_related_name = 'attachments'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.original_name


class SavedView(Timestamped):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='saved_views')
    name = models.CharField(max_length=255)
    params = models.JSONField(default=dict)

    class Meta:
        default_related_name = 'saved_views'
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class Subtask(Timestamped):
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    done = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        default_related_name = 'subtasks'
        ordering = ['position', 'id']

    def save(self, *args, **kwargs):
        if self._state.adding and not self.position:
            last = (Subtask.objects.filter(todo=self.todo)
                    .order_by('-position')
                    .values_list('position', flat=True)
                    .first())
            self.position = 0 if last is None else last + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.text


def _new_calendar_token():
    import secrets
    return secrets.token_urlsafe(32)


class CalendarFeed(Timestamped):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='calendar_feed')
    token = models.CharField(
        max_length=64, unique=True, db_index=True,
        default=_new_calendar_token)

    def __str__(self):
        return f'calendar feed for {self.user}'


class Notification(Timestamped):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=32)
    text = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, default='')
    read = models.BooleanField(default=False)

    class Meta:
        default_related_name = 'notifications'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user}: {self.text[:40]}'


class Webhook(Timestamped):
    dashboard = models.ForeignKey(
        DashBoard, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField(max_length=500)
    events = models.JSONField(default=list, blank=True)  # [] = all
    active = models.BooleanField(default=True)

    class Meta:
        default_related_name = 'webhooks'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'webhook -> {self.url}'


class UserPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='preference')
    email_on_assign = models.BooleanField(default=True)
    email_on_mention = models.BooleanField(default=True)

    def __str__(self):
        return f'prefs for {self.user}'