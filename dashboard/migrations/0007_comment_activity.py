import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_todo_position'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('body', models.TextField()),
                ('author', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to=settings.AUTH_USER_MODEL)),
                ('todo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments', to='dashboard.todo')),
            ],
            options={
                'default_related_name': 'comments',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('verb', models.CharField(max_length=32)),
                ('message', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities',
                    to=settings.AUTH_USER_MODEL)),
                ('dashboard', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activities', to='dashboard.dashboard')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
