"""Celery application for the backend project.

`celery -A backend worker` / `celery -A backend beat` pick this up via
backend/__init__.py, which exposes `celery_app`.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# All Celery settings live in Django settings under the CELERY_ namespace.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks.py in every installed app (e.g. dashboard.tasks).
app.autodiscover_tasks()
