from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0010_subtask'),
    ]

    operations = [
        migrations.AddField(
            model_name='todo',
            name='recurrence',
            field=models.CharField(
                choices=[('none', 'None'), ('daily', 'Daily'),
                         ('weekly', 'Weekly'), ('monthly', 'Monthly')],
                default='none', max_length=10),
        ),
    ]
