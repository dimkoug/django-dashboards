import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0014_todo_blockers'),
    ]

    operations = [
        migrations.CreateModel(
            name='Webhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('url', models.URLField(max_length=500)),
                ('events', models.JSONField(blank=True, default=list)),
                ('active', models.BooleanField(default=True)),
                ('dashboard', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webhooks', to='dashboard.dashboard')),
            ],
            options={
                'default_related_name': 'webhooks',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
