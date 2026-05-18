import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0009_savedview'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subtask',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('text', models.CharField(max_length=255)),
                ('done', models.BooleanField(default=False)),
                ('position', models.PositiveIntegerField(default=0)),
                ('todo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subtasks', to='dashboard.todo')),
            ],
            options={
                'default_related_name': 'subtasks',
                'ordering': ['position', 'id'],
            },
        ),
    ]
