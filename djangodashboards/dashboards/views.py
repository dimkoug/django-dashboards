from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView,UpdateView,DeleteView
# Create your views here.

from core.mixins import AjaxMixin,ModelMixin,PaginationMixin, FormMixin, SuccessUrlMixin,PassRequestToFormViewMixin


from .models import Dashboard,Column,Task,Document
from .forms import DashboardForm,ColumnForm,TaskForm



class DashboardListView(AjaxMixin,ModelMixin,PaginationMixin,LoginRequiredMixin,ListView):
    model = Dashboard
    queryset = Dashboard.objects.prefetch_related('profiles')
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().filter(profiles=self.request.user.profile)
        return queryset



class DashboardDetailView(AjaxMixin,ModelMixin,LoginRequiredMixin,DetailView):
    model = Dashboard
    queryset = Dashboard.objects.prefetch_related('profiles', 'columns')

    def get_queryset(self):
        queryset = super().get_queryset().filter(profiles=self.request.user.profile)
        return queryset


class DashboardCreateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,CreateView):
    model = Dashboard
    form_class = DashboardForm


class DashboardUpdateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,UpdateView):
    model = Dashboard
    form_class = DashboardForm
    queryset = Dashboard.objects.prefetch_related('profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(profiles=self.request.user.profile)
        return queryset


class DashboardDeleteView(AjaxMixin,ModelMixin,LoginRequiredMixin,SuccessUrlMixin,DeleteView):
    model = Dashboard
    queryset = Dashboard.objects.prefetch_related('profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(profiles=self.request.user.profile)
        return queryset


class ColumnListView(AjaxMixin,ModelMixin,PaginationMixin,LoginRequiredMixin,ListView):
    model = Column
    queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(dashboard__profiles=self.request.user.profile)
        return queryset



class ColumnDetailView(AjaxMixin,ModelMixin,LoginRequiredMixin,DetailView):
    model = Column
    queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles', 'tasks')

    def get_queryset(self):
        queryset = super().get_queryset().filter(dashboard__profiles=self.request.user.profile)
        return queryset


class ColumnCreateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,CreateView):
    model = Column
    form_class = ColumnForm

    def get_initial(self):
        initial = super().get_initial()
        if 'dashboard' in self.request.GET:
            initial['dashboard'] = self.request.GET.get('dashboard')

        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.request.GET.get('dashboard')
        if dashboard:
            back_url = reverse_lazy("dashboards:dashboard-detail",kwargs={"pk":dashboard})
            context['back_url'] = back_url
        return context

    def get_success_url(self):
        dashboard = self.request.GET.get('dashboard')
        if dashboard:
            back_url = reverse_lazy("dashboards:dashboard-detail",kwargs={"pk":dashboard})
            return back_url
        else:
            return reverse_lazy('{}:{}-list'.format(
                self.model._meta.app_label, self.model.__name__.lower()))


class ColumnUpdateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,UpdateView):
    model = Column
    form_class = ColumnForm
    queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(dashboard__profiles=self.request.user.profile)
        return queryset

    def get_success_url(self):
        back_url = reverse_lazy("dashboards:dashboard-detail",kwargs={"pk":self.object.dashboard_id})
        return back_url



class ColumnDeleteView(AjaxMixin,ModelMixin,LoginRequiredMixin,SuccessUrlMixin,DeleteView):
    model = Column
    queryset = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(dashboard__profiles=self.request.user.profile)
        return queryset


class TaskListView(AjaxMixin,ModelMixin,PaginationMixin,LoginRequiredMixin,ListView):
    model = Task
    queryset = Task.objects.select_related('column').prefetch_related('column__dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(column__dashboard__profiles=self.request.user.profile)
        return queryset



class TaskDetailView(AjaxMixin,ModelMixin,LoginRequiredMixin,DetailView):
    model = Task
    queryset = Task.objects.select_related('column').prefetch_related('column__dashboard__profiles', 'documents')

    def get_queryset(self):
        queryset = super().get_queryset().filter(column__dashboard__profiles=self.request.user.profile)
        return queryset


class TaskCreateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,CreateView):
    model = Task
    form_class = TaskForm

    def get_initial(self):
        initial = super().get_initial()
        if 'column' in self.request.GET:
            initial['column'] = self.request.GET.get('column')
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        column = self.request.GET.get('column')
        if column:
            back_url = reverse_lazy("dashboards:column-detail",kwargs={"pk":column})
            context['back_url'] = back_url
        return context
    
    def form_valid(self,form):
        obj = form.save()
        files = self.request.FILES.getlist('files')
        if files:
            for f in files:
                Document.objects.create(task=obj,document=f)
        return super().form_valid(form)

    def get_success_url(self):
        column = self.request.GET.get('column')
        if column:
            back_url = reverse_lazy("dashboards:column-detail",kwargs={"pk":column})
            return back_url
        else:
            return reverse_lazy('{}:{}-list'.format(
                self.model._meta.app_label, self.model.__name__.lower()))


class TaskUpdateView(AjaxMixin,ModelMixin,LoginRequiredMixin,FormMixin,SuccessUrlMixin,PassRequestToFormViewMixin,UpdateView):
    model = Task
    form_class = TaskForm
    queryset = Task.objects.select_related('column').prefetch_related('column__dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(column__dashboard__profiles=self.request.user.profile)
        return queryset
    
    def form_valid(self,form):
        obj = form.save()
        files = self.request.FILES.getlist('files')
        if files:
            for f in files:
                Document.objects.create(task=obj,document=f)
        return super().form_valid(form)

    def get_success_url(self):
        back_url = reverse_lazy("dashboards:column-detail",kwargs={"pk":self.object.column_id})
        return back_url



class TaskDeleteView(AjaxMixin,ModelMixin,LoginRequiredMixin,SuccessUrlMixin,DeleteView):
    model = Task
    queryset = Task.objects.select_related('column').prefetch_related('column__dashboard__profiles')

    def get_queryset(self):
        queryset = super().get_queryset().filter(column__dashboard__profiles=self.request.user.profile)
        return queryset