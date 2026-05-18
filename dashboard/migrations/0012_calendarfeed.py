import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import dashboard.models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0011_todo_recurrence'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarFeed',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('token', models.CharField(
                    db_index=True, default=dashboard.models.
                    _new_calendar_token, max_length=64, unique=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='calendar_feed',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'abstract': False},
        ),
    ]
