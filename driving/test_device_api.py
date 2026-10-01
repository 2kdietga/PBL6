from datetime import date, timedelta
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock, patch

import requests
from PIL import Image
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from vehicles.models import Device, Vehicle, VehicleType, DriverVehicleAssignment
from .face_verification import cosine_similarity
from .models import DrivingSession


@override_settings(FACE_SINGLE_EMBEDDING_URL='https://example.hf.space/extract_single',
                   FACE_SINGLE_FILE_FIELD='file', HF_API_TOKEN='', FACE_COSINE_THRESHOLD='0.75',
                   FACE_COSINE_MARGIN=0.05, DEVICE_API_REQUIRE_HTTPS=True, DEVICE_API_CHECK_FRAME_AGE=True)
class DeviceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vector = [1.0] + [0.0] * 511
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='PI-001', load_capacity=1000)
        cls.device = Device.objects.create(vehicle=cls.vehicle, device_code='pi-001', name='Pi',
                                           api_key_digest=sha256(b'device-secret').hexdigest(),
                                           api_key_hash=make_password('device-secret'))
        cls.driver = cls.create_driver('driver', cls.vector)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
                                                                 start_at=timezone.now()-timedelta(hours=1))

    @classmethod
    def create_driver(cls, username, vector):
        user = User.objects.create_user(username)
        driver = DriverProfile.objects.create(user=user, full_name=username, date_of_birth=date(1990, 1, 1),
                                               phone='123', address='City')
        DriverLicense.objects.create(driver=driver, license_number=username, license_class='B',
                                     issued_date=date(2020, 1, 1), expiry_date=timezone.localdate()+timedelta(days=30),
                                     front_image_url='https://example.com/front.jpg',
                                     back_image_url='https://example.com/back.jpg', status='ACTIVE')
        FaceProfile.objects.create(driver=driver, embedding=vector, approval_status='APPROVED',
                                   face_image_url='https://example.com/face.jpg')
        driver.approval_status = 'APPROVED'
        driver.save()
        return driver

    def setUp(self):
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer device-secret'}
        self.url = reverse('device-api:verify-face')
        output = BytesIO()
        Image.new('RGB', (640, 360), 'red').save(output, 'JPEG', quality=85)
        self.jpeg = output.getvalue()
        self.hf = self.enterContext(patch('driving.face_verification.requests.post'))
        self.response = Mock(status_code=200)
        self.response.json.return_value = {'vector': self.vector}
        self.hf.return_value.__enter__.return_value = self.response

    def post(self, *, image=None, captured_at=None, **extra):
        return self.client.post(self.url, {
            'frame': SimpleUploadedFile('frame.jpg', self.jpeg if image is None else image, 'image/jpeg'),
            'captured_at': captured_at or timezone.now().isoformat(), **extra,
        }, secure=True, **self.headers)

    def test_exact_original_jpeg_forwarded_in_one_request_without_disk(self):
        with patch('django.core.files.uploadedfile.TemporaryUploadedFile', side_effect=AssertionError('disk write')):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['code'], 'DRIVER_VERIFIED')
        self.assertTrue(body['data']['verified'])
        self.assertEqual(body['data']['driver'], {'id': self.driver.pk, 'full_name': self.driver.full_name})
        self.assertNotIn('assignment_id', body['data'])
        self.assertFalse(DrivingSession.objects.exists())
        self.assertNotIn('vector', response.content.decode())
        self.hf.assert_called_once_with('https://example.hf.space/extract_single',
            files={'file': ('frame.jpg', self.jpeg, 'image/jpeg')}, headers={}, timeout=(5, 30), allow_redirects=False)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_auth_https_and_method(self):
        for kwargs, expected in [({}, 'DEVICE_UNAUTHORIZED'),
                                  ({'HTTP_X_DEVICE_CODE': 'pi-001', 'HTTP_AUTHORIZATION': 'Bearer wrong'}, 'DEVICE_UNAUTHORIZED')]:
            self.assertEqual(self.client.post(self.url, secure=True, **kwargs).json()['code'], expected)
        self.assertEqual(self.client.post(self.url, **self.headers).json()['code'], 'HTTPS_REQUIRED')
        self.assertEqual(self.client.get(self.url, secure=True, **self.headers).status_code, 405)
        self.hf.assert_not_called()

    def test_context_has_camera_contract(self):
        body = self.client.get(reverse('device-api:context'), secure=True, **self.headers).json()
        self.assertNotIn('eligible_driver_count', body['data'])
        self.assertEqual(body['data']['device_code'], self.device.device_code)
        self.assertEqual(body['data']['frame']['quality'], 85)
        self.assertEqual(body['data']['frame']['max_width'], 1280)

    def test_token_identifies_its_own_device_and_rejects_conflicting_code(self):
        vehicle = Vehicle.objects.create(vehicle_type=self.vehicle.vehicle_type, license_plate='TOKEN-OTHER')
        Device.objects.create(vehicle=vehicle, device_code='pi-002', name='Other Pi',
                              api_key_hash=make_password('other-secret'),
                              api_key_digest=sha256(b'other-secret').hexdigest())
        url = reverse('device-api:context')
        response = self.client.get(url, secure=True, HTTP_AUTHORIZATION='Bearer other-secret')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['vehicle']['id'], vehicle.pk)
        self.assertEqual(response.json()['data']['device_code'], 'pi-002')
        response = self.client.get(url, secure=True, HTTP_AUTHORIZATION='Bearer other-secret',
                                   HTTP_X_DEVICE_CODE='pi-001')
        self.assertEqual(response.status_code, 401)
        for authorization in ['', 'Bearer ', 'Bearer unknown', 'Basic device-secret', 'Bearer ' + 'x'*257]:
            self.assertEqual(self.client.get(url, secure=True, HTTP_AUTHORIZATION=authorization).status_code, 401)

    def test_legacy_key_requires_device_code_until_rotated(self):
        Device.objects.filter(pk=self.device.pk).update(api_key_digest=None)
        self.assertEqual(self.post().status_code, 401)
        self.headers['HTTP_X_DEVICE_CODE'] = self.device.device_code
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')

    def test_token_revoked_during_verification_is_rejected(self):
        from io import StringIO
        def extract():
            call_command('rotate_device_key', self.device.device_code, revoke=True, stdout=StringIO())
            return {'vector': self.vector}
        self.response.json.side_effect = extract
        self.assertEqual(self.post().status_code, 401)

    def test_invalid_image_resolution_and_format(self):
        self.assertEqual(self.post(image=b'raw rgb or base64').json()['code'], 'INVALID_JPEG')
        self.assertEqual(self.post(image=self.jpeg[:100]).json()['code'], 'INVALID_JPEG')
        out = BytesIO()
        Image.new('RGB', (1281, 720)).save(out, 'JPEG')
        self.assertEqual(self.post(image=out.getvalue()).json()['code'], 'INVALID_RESOLUTION')
        out = BytesIO()
        Image.new('RGB', (100, 100)).save(out, 'PNG')
        self.assertEqual(self.post(image=out.getvalue()).status_code, 415)
        self.hf.assert_not_called()

    def test_large_request_and_large_file_never_use_disk(self):
        self.assertEqual(self.post(image=b'x' * (2 * 1024 * 1024 + 20000)).status_code, 413)
        self.assertEqual(self.post(image=b'x' * (2 * 1024 * 1024 + 1)).status_code, 413)
        self.hf.assert_not_called()

    def test_single_file_and_metadata_only(self):
        self.assertEqual(self.post(extra=SimpleUploadedFile('other.jpg', self.jpeg, 'image/jpeg')).json()['code'], 'INVALID_FRAME')
        self.assertEqual(self.post(driver_id='999').json()['code'], 'INVALID_FIELDS')
        response = self.client.post(self.url, {'captured_at': timezone.now().isoformat(), 'frame': [
            SimpleUploadedFile('a.jpg', self.jpeg, 'image/jpeg'),
            SimpleUploadedFile('b.jpg', self.jpeg, 'image/jpeg')]}, secure=True, **self.headers)
        self.assertEqual(response.json()['code'], 'INVALID_FRAME')
        self.hf.assert_not_called()

    def test_capture_time_and_content_type(self):
        for timestamp, code in [('invalid', 'INVALID_CAPTURE_TIME'), ('2026-01-01T12:00:00', 'INVALID_CAPTURE_TIME'),
                                ((timezone.now()-timedelta(minutes=2)).isoformat(), 'STALE_FRAME'),
                                ((timezone.now()+timedelta(minutes=2)).isoformat(), 'STALE_FRAME')]:
            self.assertEqual(self.post(captured_at=timestamp).json()['code'], code)
        self.assertEqual(self.client.post(self.url, '{}', content_type='application/json',
                                         secure=True, **self.headers).status_code, 415)
        self.hf.assert_not_called()

    def test_hf_timeout_unavailable_and_unusable_face(self):
        self.hf.side_effect = requests.Timeout()
        response = self.post()
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response['Retry-After'], '5')
        self.hf.side_effect = None
        for status, code in [(503, 'HF_UNAVAILABLE'), (429, 'HF_UNAVAILABLE'), (422, 'FACE_NOT_USABLE'),
                             (400, 'FACE_NOT_USABLE'), (401, 'HF_CONTRACT_ERROR'), (307, 'HF_CONTRACT_ERROR')]:
            self.response.status_code = status
            self.assertEqual(self.post().json()['code'], code)

    def test_invalid_hf_vectors_fail_closed(self):
        for vector in [[], [1.0]*511, [0.0]*512, [True]*512, [float('nan')]*512, [float('inf')]*512, ['1']*512]:
            self.response.json.return_value = {'vector': vector}
            self.assertEqual(self.post().json()['code'], 'INVALID_EMBEDDING')
        self.response.json.side_effect = ValueError('invalid json')
        self.assertEqual(self.post().json()['code'], 'INVALID_EMBEDDING')
        self.response.json.side_effect = requests.exceptions.JSONDecodeError('invalid json', 'x', 0)
        self.assertEqual(self.post().json()['code'], 'INVALID_EMBEDDING')

    def test_face_mismatch_is_a_completed_negative_decision(self):
        self.response.json.return_value = {'vector': [0.0, 1.0] + [0.0]*510}
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertFalse(response.json()['data']['verified'])
        self.assertIsNone(response.json()['data']['driver'])

    def test_ambiguous_drivers_rejected_but_duplicate_assignments_allowed(self):
        DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle, start_at=timezone.now())
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')
        other = self.create_driver('other', self.vector)
        DriverVehicleAssignment.objects.create(driver=other, vehicle=self.vehicle, start_at=timezone.now())
        self.assertEqual(self.post().json()['code'], 'FACE_AMBIGUOUS')

    @override_settings(DEVICE_API_REQUIRE_HTTPS=False, DEVICE_API_CHECK_FRAME_AGE=False)
    def test_http_returns_driver_without_assignment_or_session(self):
        DriverVehicleAssignment.objects.all().delete()
        self.driver.full_name = 'Nguyễn Văn An'
        self.driver.save()
        response = self.client.post(self.url, {
            'frame': SimpleUploadedFile('frame.jpg', self.jpeg, 'image/jpeg'),
            'captured_at': (timezone.now()-timedelta(minutes=2)).isoformat(),
        }, **self.headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['code'], 'DRIVER_VERIFIED')
        self.assertTrue(body['data']['verified'])
        self.assertEqual(body['data']['driver'], {'id': self.driver.pk, 'full_name': self.driver.full_name})
        self.assertEqual(body['data']['device_code'], self.device.device_code)
        self.assertNotIn('assignment_id', body['data'])
        self.assertFalse(DriverVehicleAssignment.objects.exists())
        self.assertFalse(DrivingSession.objects.exists())
        context = self.client.get(reverse('device-api:context'), **self.headers)
        self.assertEqual(context.json()['code'], 'DEVICE_READY')

    def test_driver_without_license_or_approval_can_be_identified(self):
        DriverVehicleAssignment.objects.all().delete()
        DriverLicense.objects.filter(driver=self.driver).delete()
        DriverProfile.objects.filter(pk=self.driver.pk).update(approval_status='PENDING')
        FaceProfile.objects.filter(driver=self.driver).update(approval_status='PENDING')
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')

    def test_no_face_profiles_or_empty_embeddings(self):
        FaceProfile.objects.filter(driver=self.driver).update(embedding=[])
        for remove_profile in (False, True):
            if remove_profile:
                FaceProfile.objects.filter(driver=self.driver).delete()
            response = self.post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['code'], 'DRIVER_NOT_FOUND')
            self.assertFalse(response.json()['data']['verified'])
            self.assertIsNone(response.json()['data']['driver'])

    def test_assignment_ending_during_hf_does_not_block_identification(self):
        def extract():
            DriverVehicleAssignment.objects.filter(pk=self.assignment.pk).update(end_at=timezone.now())
            return {'vector': self.vector}
        self.response.json.side_effect = extract
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')

    def test_device_reassignment_during_hf_is_rejected(self):
        other = Vehicle.objects.create(vehicle_type=self.vehicle.vehicle_type, license_plate='REASSIGNED', load_capacity=1000)
        def extract():
            Device.objects.filter(pk=self.device.pk).update(vehicle=other)
            return {'vector': self.vector}
        self.response.json.side_effect = extract
        self.assertEqual(self.post().json()['code'], 'DEVICE_ASSIGNMENT_CHANGED')

    def test_key_rotation_and_revocation(self):
        from io import StringIO
        output = StringIO()
        call_command('rotate_device_key', self.device.device_code, stdout=output)
        key = output.getvalue().strip()
        self.device.refresh_from_db()
        self.assertNotEqual(key, self.device.api_key_hash)
        self.assertEqual(self.device.api_key_digest, sha256(key.encode()).hexdigest())
        self.assertEqual(self.post().json()['code'], 'DEVICE_UNAUTHORIZED')
        self.headers['HTTP_AUTHORIZATION'] = 'Bearer ' + key
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')
        old_key = key
        output = StringIO()
        call_command('rotate_device_key', self.device.device_code, stdout=output)
        self.assertEqual(self.post().status_code, 401)
        self.headers['HTTP_AUTHORIZATION'] = 'Bearer ' + output.getvalue().strip()
        self.assertNotEqual(old_key, output.getvalue().strip())
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')
        call_command('rotate_device_key', self.device.device_code, revoke=True, stdout=StringIO())
        self.assertEqual(self.post().json()['code'], 'DEVICE_UNAUTHORIZED')
        self.device.refresh_from_db()
        self.assertIsNone(self.device.api_key_digest)

    def test_vehicle_boundary_and_device_state(self):
        vehicle = Vehicle.objects.create(vehicle_type=self.vehicle.vehicle_type, license_plate='OTHER', load_capacity=1000)
        Device.objects.filter(pk=self.device.pk).update(vehicle=vehicle)
        self.assertEqual(self.post().json()['code'], 'DRIVER_VERIFIED')
        self.hf.reset_mock()
        Device.objects.filter(pk=self.device.pk).update(status='MAINTENANCE')
        self.assertEqual(self.post().json()['code'], 'DEVICE_MAINTENANCE')
        Device.objects.filter(pk=self.device.pk).update(status='ONLINE')
        Vehicle.objects.filter(pk=vehicle.pk).update(status='INACTIVE')
        self.assertEqual(self.post().json()['code'], 'VEHICLE_INACTIVE')
        self.hf.assert_not_called()

    def test_invalid_profile_and_unconfigured_threshold(self):
        FaceProfile.objects.filter(driver=self.driver).update(embedding=[1, 2])
        self.assertEqual(self.post().json()['code'], 'PROFILE_EMBEDDING_INVALID')
        with override_settings(FACE_COSINE_THRESHOLD=''):
            self.assertEqual(self.post().json()['code'], 'MATCHING_NOT_CONFIGURED')

    def test_cosine_normalizes_and_rejects_dimensions(self):
        self.assertEqual(cosine_similarity([2.0]+[0.0]*511, self.vector), 1.0)
        self.assertEqual(cosine_similarity([-2.0]+[0.0]*511, self.vector), -1.0)
        self.assertAlmostEqual(cosine_similarity([1e308]*512, [1e308]*512), 1.0)
        with self.assertRaises(ValueError):
            cosine_similarity([1], self.vector)
