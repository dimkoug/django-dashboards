import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_rename_column_dashboard'),
    ]

    operations = [
        migrations.CreateModel(
            name='Label',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('color', models.CharField(default='#6366f1', max_length=7)),
                ('dashboard', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='labels', to='dashboard.dashboard')),
            ],
            options={
                'default_related_name': 'labels',
                'unique_together': {('dashboard', 'name')},
            },
        ),
        migrations.AddField(
            model_name='todo',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='todo',
            name='priority',
            field=models.CharField(
                choices=[('low', 'Low'), ('medium', 'Medium'),
                         ('high', 'High')],
                default='medium', max_length=10),
        ),
        migrations.AddField(
            model_name='todo',
            name='labels',
            field=models.ManyToManyField(
                blank=True, related_name='todos', to='dashboard.label'),
        ),
    ]
