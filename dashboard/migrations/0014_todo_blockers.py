from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0013_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='todo',
            name='blockers',
            field=models.ManyToManyField(
                blank=True, related_name='blocking', to='dashboard.todo'),
        ),
    ]
