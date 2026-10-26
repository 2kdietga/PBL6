from datetime import date, timedelta
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from frontend.forms import DeviceForm, LicenseForm, VehicleForm
from vehicles.models import VehicleType, Vehicle, Device, DriverVehicleAssignment
from .models import DrivingSession


@override_settings(FACE_COSINE_THRESHOLD='0.75', FACE_COSINE_MARGIN=0.05,
                   DEVICE_API_REQUIRE_HTTPS=False, DEVICE_API_CHECK_FRAME_AGE=False)
class SessionAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vector = [1.0] + [0.0] * 511
        cls.user = User.objects.create_user('session-driver')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        cls.license = DriverLicense.objects.create(driver=cls.driver, license_number='SESSION',
            license_class='B', license_standard='VN_2025', status='ACTIVE', issued_date=date(2025, 1, 1),
            expiry_date=timezone.localdate() + timedelta(days=30),
            front_image_url='https://example.com/front.jpg', back_image_url='https://example.com/back.jpg')
        cls.face = FaceProfile.objects.create(driver=cls.driver, embedding=cls.vector,
            face_image_url='https://example.com/face.jpg', approval_status='APPROVED')
        cls.driver.approval_status = 'APPROVED'
        cls.driver.save()
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='SESSION', gross_vehicle_weight=3000)
        cls.other_vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='OTHER', gross_vehicle_weight=3000)
        cls.device = Device.objects.create(vehicle=cls.vehicle, device_code='session-pi', name='Pi',
            api_key_hash=make_password('secret'), api_key_digest=sha256(b'secret').hexdigest())
        cls.other_device = Device.objects.create(vehicle=cls.other_vehicle, device_code='other-pi', name='Other',
            api_key_hash=make_password('other'), api_key_digest=sha256(b'other').hexdigest())
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=timezone.now() - timedelta(hours=1))

    def setUp(self):
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer secret'}
        self.start_url = reverse('device-api:session-start')
        self.context_url = reverse('device-api:context')
        output = BytesIO()
        Image.new('RGB', (640, 360)).save(output, 'JPEG')
        self.jpeg = output.getvalue()
        self.extract = self.enterContext(patch('driving.device_api.extract_single', return_value=self.vector))

    def start(self, **extra):
        return self.client.post(self.start_url, {
            'frame': SimpleUploadedFile('frame.jpg', self.jpeg, 'image/jpeg'),
            'captured_at': timezone.now().isoformat(), **extra,
        }, **self.headers)

    def end(self, pk, headers=None):
        return self.client.post(reverse('device-api:session-end', args=[pk]),
                                data=b'', content_type='application/octet-stream',
                                **(headers if headers is not None else self.headers))

    def test_start_context_end_and_retry(self):
        self.assertIsNone(self.client.get(self.context_url, **self.headers).json()['data']['active_session'])
        response = self.start()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()['data']
        self.assertTrue(data['verified'])
        self.assertTrue(data['session_started'])
        session = DrivingSession.objects.get(pk=data['session_id'])
        self.assertEqual(session.source_device_id, self.device.pk)
        self.assertEqual(session.assignment_id, self.assignment.pk)
        self.assertEqual(data['status'], 'STARTED')
        self.assertEqual(self.start().json()['code'], 'SESSION_ALREADY_ACTIVE')
        self.assertEqual(DrivingSession.objects.count(), 1)
        active = self.client.get(self.context_url, **self.headers).json()['data']['active_session']
        self.assertEqual(active['session_id'], session.pk)
        first_end = self.end(session.pk)
        self.assertEqual(first_end.status_code, 200)
        self.assertEqual(first_end.json()['data']['status'], 'ENDED')
        again = self.end(session.pk)
        self.assertEqual(again.json()['data']['ended_at'], first_end.json()['data']['ended_at'])
        self.assertIsNone(self.client.get(self.context_url, **self.headers).json()['data']['active_session'])
        self.assertEqual(self.start().status_code, 201)

    def test_does_not_open_when_face_does_not_match(self):
        self.extract.return_value = [0.0, 1.0] + [0.0] * 510
        result = self.start()
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['data']['verified'])
        self.assertFalse(DrivingSession.objects.exists())

    def test_start_always_requires_fresh_frame_even_in_demo_mode(self):
        response = self.start(captured_at=(timezone.now() - timedelta(minutes=2)).isoformat())
        self.assertEqual(response.json()['code'], 'STALE_FRAME')
        self.extract.assert_not_called()

    def test_client_cannot_supply_identity_or_session_time(self):
        for key in ('driver_id', 'vehicle_id', 'started_at', 'session_id'):
            with self.subTest(key=key):
                self.assertEqual(self.start(**{key: '123'}).json()['code'], 'INVALID_FIELDS')
        self.assertFalse(DrivingSession.objects.exists())

    def test_missing_expired_future_or_ambiguous_assignment(self):
        for changes in (
            {'end_at': timezone.now() - timedelta(seconds=1)},
            {'start_at': timezone.now() + timedelta(hours=1), 'end_at': None},
        ):
            DriverVehicleAssignment.objects.filter(pk=self.assignment.pk).update(**changes)
            self.assertEqual(self.start().json()['code'], 'NO_ACTIVE_ASSIGNMENT')
        DriverVehicleAssignment.objects.filter(pk=self.assignment.pk).update(start_at=timezone.now() - timedelta(hours=1))
        DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle, start_at=timezone.now())
        self.assertEqual(self.start().json()['code'], 'ASSIGNMENT_AMBIGUOUS')
        DriverVehicleAssignment.objects.all().delete()
        self.assertEqual(self.start().json()['code'], 'NO_ACTIVE_ASSIGNMENT')
        self.assertFalse(DrivingSession.objects.exists())

    def test_ineligible_profile_license_and_account(self):
        cases = [
            (User, self.user.pk, 'is_active', False),
            (DriverProfile, self.driver.pk, 'approval_status', 'PENDING'),
            (DriverProfile, self.driver.pk, 'phone', ''),
            (FaceProfile, self.face.pk, 'approval_status', 'REJECTED'),
            (DriverLicense, self.license.pk, 'expiry_date', timezone.localdate()),
            (DriverLicense, self.license.pk, 'issued_date', timezone.localdate() + timedelta(days=1)),
            (DriverLicense, self.license.pk, 'status', 'PENDING'),
            (DriverLicense, self.license.pk, 'license_standard', ''),
            (Vehicle, self.vehicle.pk, 'gross_vehicle_weight', None),
            (Vehicle, self.vehicle.pk, 'gross_vehicle_weight', 8000),
        ]
        for model, pk, field, value in cases:
            with self.subTest(model=model.__name__, field=field, value=value):
                old = getattr(model.objects.get(pk=pk), field)
                model.objects.filter(pk=pk).update(**{field: value})
                result = self.start()
                self.assertEqual(result.json()['code'], 'DRIVER_NOT_ELIGIBLE', result.content)
                data = result.json()['data']
                self.assertTrue(data['verified'])
                self.assertFalse(data['session_started'])
                self.assertIsNone(data['session_id'])
                self.assertEqual(data['driver']['id'], self.driver.pk)
                self.assertTrue(data['reason_code'])
                model.objects.filter(pk=pk).update(**{field: old})
        self.assertFalse(DrivingSession.objects.exists())

    def test_denial_reasons_and_recognized_identity(self):
        cases = [
            (User, self.user.pk, 'is_active', False, 'DRIVER_ACCOUNT_INACTIVE'),
            (DriverLicense, self.license.pk, 'expiry_date', timezone.localdate(), 'LICENSE_EXPIRED'),
            (Vehicle, self.vehicle.pk, 'gross_vehicle_weight', 8000, 'LICENSE_CLASS_INCOMPATIBLE'),
        ]
        for model, pk, field, value, reason in cases:
            with self.subTest(reason=reason):
                old = getattr(model.objects.get(pk=pk), field)
                model.objects.filter(pk=pk).update(**{field: value})
                body = self.start().json()
                self.assertEqual(body['data']['reason_code'], reason)
                self.assertEqual(body['data']['driver']['full_name'], 'Driver')
                model.objects.filter(pk=pk).update(**{field: old})
        DriverVehicleAssignment.objects.all().delete()
        body = self.start().json()
        self.assertEqual(body['data']['reason_code'], 'NO_ACTIVE_ASSIGNMENT')
        self.assertTrue(body['data']['verified'])
        self.assertFalse(DrivingSession.objects.exists())

    def test_rechecks_changes_during_hf_call(self):
        def revoke(data):
            Device.objects.filter(pk=self.device.pk).update(api_key_hash='')
            return self.vector
        self.extract.side_effect = revoke
        self.assertEqual(self.start().status_code, 401)
        self.assertFalse(DrivingSession.objects.exists())

    def test_profile_revoked_during_hf_does_not_open_session(self):
        def revoke(data):
            DriverProfile.objects.filter(pk=self.driver.pk).update(approval_status='REJECTED')
            return self.vector
        self.extract.side_effect = revoke
        self.assertEqual(self.start().json()['code'], 'DRIVER_NOT_ELIGIBLE')
        self.assertFalse(DrivingSession.objects.exists())

    def test_changed_embedding_after_match_does_not_open_session(self):
        from .face_verification import match_driver
        def change(vector, threshold, margin):
            result = match_driver(vector, threshold, margin)
            FaceProfile.objects.filter(pk=self.face.pk).update(embedding=[0.0, 1.0] + [0.0] * 510)
            return result
        with patch('driving.device_api.match_driver', side_effect=change):
            self.assertEqual(self.start().json()['code'], 'DRIVER_NOT_ELIGIBLE')
        self.assertFalse(DrivingSession.objects.exists())

    def test_ownership_and_legacy_sessions(self):
        pk = self.start().json()['data']['session_id']
        other_headers = {'HTTP_AUTHORIZATION': 'Bearer other'}
        self.assertEqual(self.end(pk, other_headers).status_code, 404)
        self.assertIsNone(self.client.get(self.context_url, **other_headers).json()['data']['active_session'])
        self.assertEqual(self.end(999999).status_code, 404)
        self.end(pk)
        legacy = DrivingSession.objects.create(assignment=self.assignment, started_at=timezone.now())
        self.assertEqual(self.end(legacy.pk).status_code, 404)
        self.assertEqual(self.start().json()['code'], 'SESSION_ALREADY_ACTIVE')

    def test_end_and_context_work_after_suspension_or_missing_matching_config(self):
        pk = self.start().json()['data']['session_id']
        Device.objects.filter(pk=self.device.pk).update(status='MAINTENANCE')
        Vehicle.objects.filter(pk=self.vehicle.pk).update(status='INACTIVE')
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        with override_settings(FACE_COSINE_THRESHOLD=''):
            context = self.client.get(self.context_url, **self.headers)
            self.assertEqual(context.status_code, 200)
            self.assertEqual(context.json()['data']['active_session']['session_id'], pk)
            self.assertIsNone(context.json()['data']['matching']['threshold'])
            self.assertEqual(self.end(pk).status_code, 200)

    def test_auth_methods_and_end_payload(self):
        self.assertEqual(self.client.post(self.start_url).status_code, 401)
        self.assertEqual(self.client.get(self.start_url, **self.headers).status_code, 405)
        pk = self.start().json()['data']['session_id']
        self.assertEqual(self.end(pk, {}).status_code, 401)
        url = reverse('device-api:session-end', args=[pk])
        self.assertEqual(self.client.get(url, **self.headers).status_code, 405)
        self.assertEqual(self.client.post(url, {'ended_at': 'fake'}, **self.headers).status_code, 400)
        self.assertEqual(DrivingSession.objects.get(pk=pk).status, 'STARTED')

    def test_device_cannot_move_or_be_deleted_with_session_history(self):
        pk = self.start().json()['data']['session_id']
        spare = Vehicle.objects.create(vehicle_type=self.vehicle.vehicle_type, license_plate='SPARE')
        payload = dict(device_code=self.device.device_code, name='Pi', vehicle=spare.pk, status='ONLINE')
        form = DeviceForm(payload, instance=Device.objects.get(pk=self.device.pk))
        self.assertFalse(form.is_valid())
        self.device.vehicle = spare
        with self.assertRaises(ValidationError):
            self.device.save()
        self.end(pk)
        self.device.save()
        # Origin remains stable after moving the hardware to another vehicle.
        self.assertEqual(self.end(pk).status_code, 200)
        with self.assertRaises(ProtectedError):
            self.device.delete()

    def test_source_device_is_immutable(self):
        pk = self.start().json()['data']['session_id']
        session = DrivingSession.objects.get(pk=pk)
        session.source_device = self.other_device
        with self.assertRaises(ValidationError):
            session.save()

    def test_web_exposes_session_eligibility_fields(self):
        self.assertIn('license_standard', LicenseForm().fields)
        self.assertIn('gross_vehicle_weight', VehicleForm().fields)
        self.assertIn('is_sleeper', VehicleForm().fields)
