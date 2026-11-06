"""Shared key generation for web provisioning and the management command."""
import secrets
from hashlib import sha256

from django.contrib.auth.hashers import make_password


def replace_key(device, *, revoke=False):
    secret = '' if revoke else secrets.token_urlsafe(32)
    device.api_key_hash = make_password(secret) if secret else ''
    device.api_key_digest = sha256(secret.encode()).hexdigest() if secret else None
    device.save(update_fields=['api_key_hash', 'api_key_digest', 'updated_at'])
    return secret
