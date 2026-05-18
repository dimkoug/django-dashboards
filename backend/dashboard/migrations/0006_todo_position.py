from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_label_todo_description_priority_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='todo',
            name='position',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='todo',
            options={'default_related_name': 'todos',
                     'ordering': ['position', 'id']},
        ),
    ]
