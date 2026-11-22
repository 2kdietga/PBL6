from django.db import models
from .protocol import defaults


class AIConfig(models.Model):
    device = models.OneToOneField('vehicles.Device', on_delete=models.CASCADE, related_name='ai_config')
    parameters = models.JSONField(default=defaults)
    desired_version = models.PositiveIntegerField(default=1)
    applied_version = models.PositiveIntegerField(default=0)
    applied_parameters = models.JSONField(default=dict)
    sync_status = models.CharField(max_length=10, default='pending', choices=[('pending', 'Chờ gửi'), ('sent', 'Chờ xác nhận'), ('applied', 'Đã áp dụng'), ('rejected', 'Bị từ chối')])
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)


class DeviceConnection(models.Model):
    device = models.OneToOneField('vehicles.Device', on_delete=models.CASCADE, related_name='mqtt_connection')
    connection_state = models.CharField(max_length=10, default='unknown')
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_online_at = models.DateTimeField(null=True, blank=True)
    last_offline_at = models.DateTimeField(null=True, blank=True)
    ai_running = models.BooleanField(default=False)
    runtime_config_version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class WorkerHealth(models.Model):
    # Singleton for the one supported worker deployment.
    connected = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True)
    connected_at = models.DateTimeField(null=True)
    owner = models.CharField(max_length=32, blank=True)
    lease_until = models.DateTimeField(null=True)


class DeviceEvent(models.Model):
    device = models.ForeignKey('vehicles.Device', on_delete=models.CASCADE, related_name='mqtt_events')
    message = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
