from django.urls import path

from . import views, functions

app_name = 'dashboards'


urlpatterns = [
    path('',views.DashboardListView.as_view(),name='dashboard-list'),
    path('create/',views.DashboardCreateView.as_view(),name='dashboard-create'),
    path('<int:pk>/',views.DashboardDetailView.as_view(),name='dashboard-detail'),
    path('update/<int:pk>/',views.DashboardUpdateView.as_view(),name='dashboard-update'),
    path('delete/<int:pk>/',views.DashboardDeleteView.as_view(),name='dashboard-delete'),

    path('columns/',views.ColumnListView.as_view(),name='column-list'),
    path('column/create/',views.ColumnCreateView.as_view(),name='column-create'),
    path('column/<int:pk>/',views.ColumnDetailView.as_view(),name='column-detail'),
    path('column/update/<int:pk>/',views.ColumnUpdateView.as_view(),name='column-update'),
    path('column/delete/<int:pk>/',views.ColumnDeleteView.as_view(),name='column-delete'),

    path('tasks/',views.TaskListView.as_view(),name='task-list'),
    path('task/create/',views.TaskCreateView.as_view(),name='task-create'),
    path('task/<int:pk>/',views.TaskDetailView.as_view(),name='task-detail'),
    path('task/update/<int:pk>/',views.TaskUpdateView.as_view(),name='task-update'),
    path('task/delete/<int:pk>/',views.TaskDeleteView.as_view(),name='task-delete'),


    path('sb/dashboards/',functions.get_dashboard_for_sb,name='sb-dashboards'),
    path('sb/columns/',functions.get_column_for_sb,name='sb-columns'),
    path('document/<int:pk>/delete/',functions.delete_document,name='delete-document'),

]
