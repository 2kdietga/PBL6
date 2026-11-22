import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import CommandError


def create_client(client_id=None):
    if not all((settings.MQTT_HOST, settings.MQTT_USERNAME, settings.MQTT_PASSWORD)):
        raise CommandError('Set MQTT_HOST, MQTT_USERNAME and MQTT_PASSWORD in the environment.')
    if not 1 <= settings.MQTT_PORT <= 65535:
        raise CommandError('MQTT_PORT must be between 1 and 65535.')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id or settings.MQTT_CLIENT_ID)
    client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    client.tls_set(ca_certs=settings.MQTT_CA_CERT)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.max_queued_messages_set(100)
    return client
