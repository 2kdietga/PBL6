"""Named frontend routes; keep API URLs in their respective Django apps."""
from django.urls import path

from .views import FrontendView

app_name = 'frontend'

PAGE_NAMES = (
    'dashboard', 'drivers', 'vehicles', 'assignments', 'sessions',
    'violations', 'appeals', 'devices', 'catalogs', 'profile',
    'license', 'face', 'login', 'register',
)

urlpatterns = [path('', FrontendView.as_view(), name='home')]
urlpatterns += [
    path(f'{page}/', FrontendView.as_view(), name=page)
    for page in PAGE_NAMES
]
