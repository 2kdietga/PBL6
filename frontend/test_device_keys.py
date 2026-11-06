from hashlib import sha256

from django.contrib.auth.hashers import check_password
from django.test import Client, TestCase
from django.urls import reverse

from accounts.concurrency import revision
from accounts.models import User
from vehicles.models import Device, Vehicle, VehicleType


class DeviceKeyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('key-admin', role='ADMIN')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='KEY-001', load_capacity=1000)
        self.device = Device.objects.create(vehicle=vehicle, device_code='PI-KEY', name='Pi')
        self.url = reverse('frontend:device-key', args=[self.device.pk])
        self.edit = reverse('frontend:edit', args=['devices', self.device.pk])
        self.client.force_login(self.admin)

    def change(self, action):
        self.device.refresh_from_db()
        return self.client.post(self.url, {'action': action, 'version': revision(self.device)})

    def test_issue_rotate_revoke_and_api_authentication(self):
        self.assertContains(self.client.get(self.edit), 'Cấp token')
        result = self.change('issue')
        secret = result.context['device_token']
        self.assertIn('no-store', result['Cache-Control'])
        self.device.refresh_from_db()
        self.assertTrue(check_password(secret, self.device.api_key_hash))
        self.assertEqual(self.device.api_key_digest, sha256(secret.encode()).hexdigest())
        self.assertNotContains(self.client.get(self.edit), secret)
        self.assertNotIn(secret, str(dict(self.client.session)))
        context = reverse('device-api:context')
        def authenticate(token):
            return self.client.get(context, secure=True, HTTP_AUTHORIZATION='Bearer ' + token).status_code
        self.assertEqual(authenticate(secret), 200)
        rotated = self.change('rotate').context['device_token']
        self.assertNotEqual(secret, rotated)
        self.assertEqual(authenticate(secret), 401)
        self.assertEqual(authenticate(rotated), 200)
        self.assertEqual(self.change('revoke').status_code, 302)
        self.assertEqual(authenticate(rotated), 401)

    def test_stale_form_cannot_rotate_again(self):
        payload = {'action': 'issue', 'version': revision(self.device)}
        self.client.post(self.url, payload)
        self.device.refresh_from_db()
        digest = self.device.api_key_digest
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.device.refresh_from_db()
        self.assertEqual(digest, self.device.api_key_digest)

    def test_permissions_method_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.change('invalid').status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(self.url, {'action': 'issue'}).status_code, 403)
        self.client.force_login(User.objects.create_user('ordinary-driver'))
        self.assertEqual(self.change('issue').status_code, 403)
        self.assertEqual(self.client.get(self.edit).status_code, 403)
        self.client.logout()
        self.assertEqual(self.change('issue').status_code, 302)
        self.device.refresh_from_db()
        self.assertFalse(self.device.api_key_hash)
