from django.db import models

# Create your models here.
from core.models import Timestamped
from core.storage import OverwriteStorage
from profiles.models import Profile

class Dashboard(Timestamped):
    name = models.CharField(max_length=255)
    profiles = models.ManyToManyField(Profile)

    class Meta:
        default_related_name = 'dashboards'
        verbose_name = 'dashboard'
        verbose_name_plural = 'dashboards'
    
    def __str__(self):
        return self.name
    

class Column(Timestamped):
    name = models.CharField(max_length=255)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE)

    class Meta:
        default_related_name = 'columns'
        verbose_name = 'column'
        verbose_name_plural = 'columns'
    
    def __str__(self):
        return self.name


class Task(Timestamped):
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    is_completed = models.BooleanField()
    column = models.ForeignKey(Column, on_delete=models.CASCADE)

    class Meta:
        default_related_name = 'tasks'
        verbose_name = 'task'
        verbose_name_plural = 'tasks'
    
    def __str__(self):
        return self.name
    

class Document(Timestamped):
    document = models.FileField(upload_to='documents/',storage=OverwriteStorage())
    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    class Meta:
        default_related_name = 'documents'
        verbose_name = 'document'
        verbose_name_plural = 'documents'
    
    def __str__(self):
        return self.document.name