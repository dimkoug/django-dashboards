from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import views

router = DefaultRouter()
router.register('dashboards', views.DashBoardViewSet, basename='dashboard')
router.register('columns', views.ColumnViewSet, basename='column')
router.register('labels', views.LabelViewSet, basename='label')
router.register('comments', views.CommentViewSet, basename='comment')
router.register('attachments', views.AttachmentViewSet,
                basename='attachment')
router.register('saved-views', views.SavedViewViewSet,
                basename='saved-view')
router.register('subtasks', views.SubtaskViewSet, basename='subtask')
router.register('notifications', views.NotificationViewSet,
                basename='notification')
router.register('webhooks', views.WebhookViewSet, basename='webhook')
router.register('todos', views.TodoViewSet, basename='todo')

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('activity/', views.ActivityListView.as_view(), name='activity'),
    path('search/', views.GlobalSearchView.as_view(), name='search'),
    path('calendar/feed/', views.CalendarFeedView.as_view(),
         name='calendar-feed'),
    path('calendar/<str:token>.ics', views.CalendarICSView.as_view(),
         name='calendar-ics'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/change-password/', views.ChangePasswordView.as_view(),
         name='change-password'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('ws-ticket/', views.WSTicketView.as_view(), name='ws-ticket'),
    path('auth/preferences/', views.PreferenceView.as_view(),
         name='preferences'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]

urlpatterns += router.urls
