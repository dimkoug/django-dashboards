import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_comment_activity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(
                    upload_to='attachments/%Y/%m/')),
                ('original_name', models.CharField(max_length=255)),
                ('todo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments', to='dashboard.todo')),
                ('uploaded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='attachments',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'default_related_name': 'attachments',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
