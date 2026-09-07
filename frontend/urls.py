from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.SignIn.as_view(), name='login'),
    path('logout/', views.SignOut.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('face/', views.profile, name='face'),
    path('license/', views.license_page, name='license'),
    path('drivers/<int:pk>/', views.driver_detail, name='driver-detail'),
    path('drivers/<int:pk>/action/', views.driver_action, name='driver-action'),
    path('manage/<str:key>/new/', views.edit, name='create'),
    path('manage/<str:key>/<int:pk>/', views.edit, name='edit'),
]
urlpatterns += [path(f'{key}/', views.listing, {'key': key}, name=key) for key in views.ENTITIES]
urlpatterns += [path(f'{key}/', views.deferred, {'title': title}, name=key) for key, title in [('violations', 'Vi phạm'), ('appeals', 'Kháng cáo')]]
