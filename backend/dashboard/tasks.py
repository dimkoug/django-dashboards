"""Celery tasks for the dashboard app."""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.management import call_command

logger = get_task_logger(__name__)


@shared_task(name='dashboard.tasks.send_due_reminders')
def send_due_reminders():
    """Run the notify_due management command (single source of truth).

    Scheduled by Celery beat (see CELERY_BEAT_SCHEDULE). Idempotent — the
    command skips recipients who already have the exact reminder.
    """
    logger.info('Running due-reminder sweep')
    call_command('notify_due')
