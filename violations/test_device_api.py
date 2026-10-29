from datetime import date, timedelta
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.media_services import MediaError
from accounts.models import User, DriverProfile
from driving.models import DrivingSession
from vehicles.models import Device, Vehicle, VehicleType, DriverVehicleAssignment
from .models import Violation, ViolationType, Evidence


@override_settings(DEVICE_API_REQUIRE_HTTPS=False)
class DeviceViolationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('pi-driver')
        driver = DriverProfile.objects.create(user=user, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='PI-TEST')
        self.device = Device.objects.create(vehicle=vehicle, device_code='PI', name='Pi',
            api_key_hash=make_password('secret'), api_key_digest=sha256(b'secret').hexdigest())
        assignment = DriverVehicleAssignment.objects.create(driver=driver, vehicle=vehicle,
            start_at=timezone.now() - timedelta(hours=2))
        self.session = DrivingSession.objects.create(assignment=assignment, source_device=self.device,
            started_at=timezone.now() - timedelta(hours=1))
        ViolationType.objects.create(code='DROWSINESS', name='Buồn ngủ')
        self.url = reverse('device-api:violation-record')
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer secret'}
        self.payload = dict(event_id=str(uuid4()), session_id=str(self.session.pk),
            violation_code='DROWSINESS', detected_at=timezone.now().isoformat(), confidence='0.94')
        output = BytesIO()
        Image.new('RGB', (640, 360)).save(output, 'JPEG')
        self.jpeg = output.getvalue()
        self.upload = self.enterContext(patch('violations.device_api.upload_image',
            return_value=('https://example.com/evidence.jpg', 'unique-id')))
        self.cleanup = self.enterContext(patch('violations.device_api.delete_images'))

    def send(self, **overrides):
        payload = {**self.payload, 'image': SimpleUploadedFile('event.jpg', self.jpeg, 'image/jpeg'), **overrides}
        return self.client.post(self.url, payload, **self.headers)

    def test_create_retry_and_admin_reviewed_retry(self):
        response = self.send()
        self.assertEqual(response.status_code, 201, response.content)
        violation = Violation.objects.get()
        self.assertEqual(violation.status, 'PENDING')
        self.assertEqual(violation.source_device, self.device)
        self.assertEqual(violation.session, self.session)
        self.assertEqual(violation.confidence, 0.94)
        self.assertEqual(violation.severity, 'MEDIUM')
        self.assertEqual(Evidence.objects.get().violation, violation)
        self.assertEqual(self.send().json()['code'], 'EVENT_ALREADY_RECORDED')
        violation.status = 'APPROVED'
        violation.save()
        self.assertEqual(self.send().json()['data']['status'], 'APPROVED')
        self.assertEqual(Violation.objects.count(), 1)
        self.upload.assert_called_once()
        self.cleanup.assert_not_called()

    def test_invalid_token_and_wrong_session_owner(self):
        self.headers['HTTP_AUTHORIZATION'] = 'Bearer wrong'
        self.assertEqual(self.send().status_code, 401)
        self.headers['HTTP_AUTHORIZATION'] = 'Bearer secret'
        DrivingSession.objects.filter(pk=self.session.pk).update(source_device=None)
        self.assertEqual(self.send().status_code, 404)
        self.upload.assert_not_called()

    def test_reject_invalid_payload_image_and_time(self):
        cases = [({'confidence': 'nan'}, 400), ({'confidence': '1.1'}, 400),
            ({'event_id': 'bad'}, 400), ({'session_id': '-1'}, 400),
            ({'detected_at': '2026-01-01T00:00:00'}, 400),
            ({'status': 'APPROVED'}, 400), ({'violation_code': 'UNKNOWN'}, 422),
            ({'detected_at': (timezone.now() + timedelta(minutes=1)).isoformat()}, 422),
            ({'detected_at': (timezone.now() - timedelta(hours=2)).isoformat()}, 422),
            ({'image': SimpleUploadedFile('x.jpg', b'broken', 'image/jpeg')}, 415),
            ({'image': SimpleUploadedFile('x.jpg', b'x' * (2 * 1024 * 1024 + 1), 'image/jpeg')}, 413)]
        for payload, expected in cases:
            with self.subTest(payload=list(payload)):
                self.assertEqual(self.send(**payload).status_code, expected)
        self.assertFalse(Violation.objects.exists())
        self.upload.assert_not_called()

    def test_ended_session_accepts_only_events_inside_session(self):
        self.session.ended_at = timezone.now() - timedelta(minutes=1)
        self.session.status = 'ENDED'
        self.session.save()
        self.assertEqual(self.send().status_code, 422)
        self.device.status = 'MAINTENANCE'
        self.device.save()
        self.assertEqual(self.send(detected_at=(timezone.now() - timedelta(minutes=2)).isoformat()).status_code, 201)

    def test_storage_failure_and_database_failure_leave_no_partial_record(self):
        self.upload.side_effect = MediaError('offline')
        response = self.send()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['retry_after_seconds'], 5)
        self.assertFalse(Violation.objects.exists())
        self.upload.side_effect = None
        with patch('violations.device_api.Evidence.objects.create', side_effect=IntegrityError('failed')):
            self.assertEqual(self.send().json()['code'], 'DATABASE_UNAVAILABLE')
        self.assertFalse(Violation.objects.exists())
        self.cleanup.assert_called_once_with(['unique-id'])

    def test_revoked_key_during_upload_cleans_image(self):
        def revoke(*args):
            Device.objects.filter(pk=self.device.pk).update(api_key_hash='revoked')
            return 'https://example.com/evidence.jpg', 'unique-id'
        self.upload.side_effect = revoke
        self.assertEqual(self.send().status_code, 401)
        self.assertFalse(Violation.objects.exists())
        self.cleanup.assert_called_once_with(['unique-id'])

    def test_duplicate_committed_during_upload_is_not_created_again(self):
        def concurrent_event(*args):
            Violation.objects.create(source_device=self.device, event_id=self.payload['event_id'],
                session=self.session, violation_type=ViolationType.objects.get(),
                detected_at=timezone.now(), severity='MEDIUM')
            return 'https://example.com/evidence.jpg', 'redundant-upload'
        self.upload.side_effect = concurrent_event
        self.assertEqual(self.send().json()['code'], 'EVENT_ALREADY_RECORDED')
        self.assertEqual(Violation.objects.count(), 1)
        self.cleanup.assert_called_once_with(['redundant-upload'])

    def test_database_uniqueness(self):
        self.send()
        with self.assertRaises(IntegrityError):
            from django.db import transaction
            with transaction.atomic():
                Violation.objects.create(source_device=self.device, event_id=self.payload['event_id'],
                    session=self.session, violation_type=ViolationType.objects.get(),
                    detected_at=timezone.now(), severity='MEDIUM')
