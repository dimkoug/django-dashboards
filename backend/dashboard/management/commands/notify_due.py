"""Reminders for todos that are overdue or due soon.

Run periodically (cron / scheduled task), e.g. hourly:

    python manage.py notify_due

Each open, assigned todo whose end_date is in the past ('due_overdue')
or within --within-hours ('due_soon') produces one notification per
assignee: persisted + real-time event + email (gated by the user's
email_on_due preference). Idempotent — a recipient who already has the
exact reminder is skipped, so repeated runs don't spam.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Notification, Todo
from dashboard.serializers import due_reminder_text, notify_due


class Command(BaseCommand):
    help = 'Notify assignees about overdue / due-soon todos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--within-hours', type=int, default=24,
            help='Hours ahead that counts as "due soon" (default 24).')

    def handle(self, *args, **options):
        now = timezone.now()
        soon_cutoff = now + timedelta(hours=options['within_hours'])

        todos = (
            Todo.objects
            .filter(completed=False, end_date__isnull=False,
                    end_date__lte=soon_cutoff)
            .select_related('column', 'column__dashboard')
            .prefetch_related('users')
        )

        sent = 0
        for todo in todos:
            overdue = todo.end_date < now
            kind = 'due_overdue' if overdue else 'due_soon'
            text = due_reminder_text(todo, overdue)
            assignee_ids = list(todo.users.values_list('id', flat=True))
            if not assignee_ids:
                continue
            # Skip recipients who already have this exact reminder.
            already = set(
                Notification.objects
                .filter(user_id__in=assignee_ids, kind=kind, text=text)
                .values_list('user_id', flat=True)
            )
            recipients = [uid for uid in assignee_ids if uid not in already]
            if not recipients:
                continue
            notify_due(todo, recipients, overdue=overdue)
            sent += len(recipients)

        self.stdout.write(self.style.SUCCESS(
            f'due reminders sent: {sent}'))
