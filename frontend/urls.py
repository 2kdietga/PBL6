from django.urls import path
from . import views
from violations import views as violation_views

app_name = 'frontend'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.SignIn.as_view(), name='login'),
    path('logout/', views.SignOut.as_view(), name='logout'),
    path('password/change/', views.ChangePassword.as_view(), name='password-change'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('face/', views.profile, name='face'),
    path('license/', views.license_page, name='license'),
    path('drivers/<int:pk>/', views.driver_detail, name='driver-detail'),
    path('drivers/<int:pk>/action/', views.driver_action, name='driver-action'),
    path('manage/<str:key>/new/', views.edit, name='create'),
    path('manage/<str:key>/<int:pk>/', views.edit, name='edit'),
    path('manage/<str:key>/bulk-delete/', views.bulk_delete, name='bulk-delete'),
    path('assignments/<int:pk>/end/', views.end_assignment, name='assignment-end'),
    path('violations/', violation_views.listing, name='violations'),
    path('violations/<int:pk>/', violation_views.detail, name='violation-detail'),
    path('violations/<int:pk>/review/', violation_views.review, name='violation-review'),
]
urlpatterns += [path(f'{key}/', views.listing, {'key': key}, name=key) for key in views.ENTITIES]
urlpatterns += [path('appeals/', views.deferred, {'title': 'Kháng cáo'}, name='appeals')]
