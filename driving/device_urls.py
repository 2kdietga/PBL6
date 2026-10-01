from django.urls import path

from . import device_api

app_name = 'device-api'
urlpatterns = [
    path('context/', device_api.context, name='context'),
    path('face-verifications/', device_api.verify_face, name='verify-face'),
]
