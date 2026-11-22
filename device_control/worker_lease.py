from datetime import timedelta
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from .models import WorkerHealth


@transaction.atomic
def acquire(owner):
    WorkerHealth.objects.get_or_create(pk=1)
    health = WorkerHealth.objects.select_for_update().get(pk=1)
    now = timezone.now()
    if health.owner and health.lease_until and health.lease_until > now:
        raise CommandError('Another MQTT worker holds the database lease. Stop it before starting a replacement.')
    health.owner = owner
    health.lease_until = now + timedelta(seconds=30)
    health.connected = False
    health.last_seen_at = now
    health.connected_at = None
    health.save()


def renew(owner, connected, connected_at):
    now = timezone.now()
    updated = WorkerHealth.objects.filter(pk=1, owner=owner, lease_until__gt=now).update(
        connected=connected, last_seen_at=now, connected_at=connected_at,
        lease_until=now + timedelta(seconds=30))
    if not updated:
        raise CommandError('MQTT worker lease expired or changed; stopping to prevent concurrent publishers.')


def release(owner):
    WorkerHealth.objects.filter(pk=1, owner=owner).update(
        owner='', lease_until=None, connected=False, last_seen_at=timezone.now())
