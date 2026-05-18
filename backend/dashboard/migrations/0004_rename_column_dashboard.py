from django.db import migrations


class Migration(migrations.Migration):
    """Fix the `dasboard` typo: Column.dasboard -> Column.dashboard."""

    dependencies = [
        ('dashboard', '0003_todo_users'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='column',
            unique_together=set(),
        ),
        migrations.RenameField(
            model_name='column',
            old_name='dasboard',
            new_name='dashboard',
        ),
        migrations.AlterUniqueTogether(
            name='column',
            unique_together={('dashboard', 'name')},
        ),
    ]
