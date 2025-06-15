from django import forms

from core.forms import BootstrapForm

from .models import Dashboard,Column,Task


class DashboardForm(BootstrapForm,forms.ModelForm):
    class Meta:
        model = Dashboard
        fields = ('name',)
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)


    def clean_name(self):
        data = self.cleaned_data['name']
        if Dashboard.objects.prefetch_related('profiles').filter(name=data,profiles=self.request.user.profile).exists():
            raise forms.ValidationError(f"{data} exists for user {self.request.user.email}")
        return data

    


class ColumnForm(BootstrapForm,forms.ModelForm):
    class Meta:
        model = Column
        fields = ('name','dashboard')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields['dashboard'].queryset = Dashboard.objects.prefetch_related('profiles').filter(
                profiles=self.request.user.profile)
        

        if 'dashboard' in self.data:
            self.fields['dashboard'].queryset = Dashboard.objects.prefetch_related('profiles').filter(
                profiles=self.request.user.profile)
        
        if self.instance.pk:
            self.fields['dashboard'].queryset = Dashboard.objects.prefetch_related('profiles').filter(
                profiles=self.request.user.profile,id=self.instance.dashboard_id)



class TaskForm(BootstrapForm,forms.ModelForm):
    class Meta:
        model = Task
        fields = ('name','column','start_date','is_completed')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields['column'].queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles').filter(
                dashboard__profiles=self.request.user.profile)
        
        if 'column' in self.data:
            self.fields['column'].queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles').filter(
                dashboard__profiles=self.request.user.profile)
        
        if self.instance.pk:
            self.fields['column'].queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles').filter(
                dashboard__profiles=self.request.user.profile,id=self.instance.column_id)