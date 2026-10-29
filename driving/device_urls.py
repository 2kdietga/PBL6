from django.urls import path

from . import device_api
from . import session_api
from violations import device_api as violation_api

app_name = 'device-api'
urlpatterns = [
    path('violations/', violation_api.record, name='violation-record'),
    path('context/', device_api.context, name='context'),
    path('face-verifications/', device_api.verify_face, name='verify-face'),
    path('sessions/start/', session_api.start, name='session-start'),
    path('sessions/<int:pk>/end/', session_api.end, name='session-end'),
]
