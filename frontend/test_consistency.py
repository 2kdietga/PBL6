from datetime import date, timedelta
from unittest.mock import patch
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from accounts.concurrency import revision
from accounts.profile_services import save_profile, save_license
from vehicles.models import Vehicle, VehicleType, DriverVehicleAssignment
from .forms import ProfileForm, LicenseForm, AssignmentForm
from .test_uploads import image_file


class ConsistencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('manager', password='ManagerPassword123!')
        cls.user = User.objects.create_user('driver', password='DriverPassword123!')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Minh', date_of_birth=date(1990, 1, 1), phone='0905111111', address='Đà Nẵng', approval_status='APPROVED')
        cls.face = FaceProfile.objects.create(driver=cls.driver, face_image_url='https://example.com/old.jpg', embedding=[1, 2], approval_status='PENDING')
        cls.license = DriverLicense.objects.create(driver=cls.driver, license_number='123456', license_class='C', issued_date=date(2025, 1, 1), expiry_date=timezone.localdate()+timedelta(days=365), front_image_url='https://example.com/front.jpg', back_image_url='https://example.com/back.jpg')
        kind = VehicleType.objects.create(name='Xe tải', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(license_plate='43C-12345', vehicle_type=kind, load_capacity=5000)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle, start_at=timezone.now()-timedelta(days=2))

    def profile_payload(self):
        obj = self.driver
        return dict(full_name=obj.full_name, date_of_birth=obj.date_of_birth, phone=obj.phone, address=obj.address, version=revision(obj))

    def test_admin_password_creation_and_change(self):
        request = RequestFactory().get('/admin/accounts/user/add/')
        request.user = self.admin
        account_admin = admin.site._registry[User]
        form = account_admin.get_form(request)(data=dict(username='newaccount', email='new@example.com', role='ADMIN', usable_password='true', password1='UniquePassword123!', password2='UniquePassword123!'))
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        self.assertTrue(account.check_password('UniquePassword123!'))
        self.assertNotEqual(account.password, 'UniquePassword123!')
        edit_form = account_admin.get_form(request, account)(instance=account)
        self.assertEqual(type(edit_form.fields['password']).__name__, 'ReadOnlyPasswordHashField')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:auth_user_password_change', args=[account.pk]), dict(password1='ChangedPassword123!', password2='ChangedPassword123!', usable_password='true'))
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertTrue(account.check_password('ChangedPassword123!'))

    def test_all_approvals_reject_stale_or_missing_version(self):
        self.client.force_login(self.admin)
        url = reverse('frontend:driver-action', args=[self.driver.pk])
        for obj, action in ((self.driver, 'approve'), (self.face, 'face-approve'), (self.license, 'license-approve')):
            old_version = revision(obj)
            obj.save()
            field = 'status' if isinstance(obj, DriverLicense) else 'approval_status'
            previous = getattr(obj, field)
            for token in (old_version, ''):
                self.client.post(url, {'action': action, 'version': token})
                obj.refresh_from_db()
                self.assertEqual(getattr(obj, field), previous)
            self.client.post(url, {'action': action, 'version': revision(obj)})
            obj.refresh_from_db()
            self.assertEqual(getattr(obj, field), 'ACTIVE' if isinstance(obj, DriverLicense) else 'APPROVED')

    def test_replacement_face_cannot_be_approved_from_old_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('frontend:driver-detail', args=[self.driver.pk]))
        token = response.context['face_version']
        self.face.face_image_url = 'https://example.com/new.jpg'
        self.face.save()
        self.client.post(reverse('frontend:driver-action', args=[self.driver.pk]), {'action': 'face-approve', 'version': token})
        self.face.refresh_from_db()
        self.assertEqual(self.face.approval_status, 'PENDING')

    def test_stale_profile_rejected_before_upload(self):
        self.client.force_login(self.user)
        payload = self.profile_payload()
        self.driver.full_name = 'New name'
        self.driver.save()
        with patch('accounts.profile_services.extract_embedding') as extract:
            response = self.client.post(reverse('frontend:profile'), {**payload, 'avatar': image_file()})
        extract.assert_not_called()
        self.assertContains(response, 'Vui lòng tải lại trang')
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.full_name, 'New name')

    def test_inflight_profile_cannot_restore_old_approved_name(self):
        first = ProfileForm({**self.profile_payload(), 'full_name': 'New reviewed name'}, instance=DriverProfile.objects.get(pk=self.driver.pk))
        late = ProfileForm({**self.profile_payload(), 'phone': '0905999999'}, instance=DriverProfile.objects.get(pk=self.driver.pk))
        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(late.is_valid(), late.errors)
        save_profile(first, self.user)
        current = DriverProfile.objects.get(pk=self.driver.pk)
        current.approval_status = 'APPROVED'
        current.save()
        with self.assertRaises(ValidationError):
            save_profile(late, self.user)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.full_name, 'New reviewed name')
        self.assertEqual(self.driver.approval_status, 'APPROVED')

    def test_license_conflict_cleans_new_upload(self):
        payload = dict(license_number=self.license.license_number, license_class='D', issued_date=self.license.issued_date, expiry_date=self.license.expiry_date, version=revision(self.license))
        form = LicenseForm(payload, {'front_image': image_file()}, instance=DriverLicense.objects.get(pk=self.license.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.license.license_class = 'C1'
        self.license.save()
        with patch('accounts.profile_services.upload_image', return_value=('https://example.com/new.jpg', 'new-id')), patch('accounts.profile_services.delete_images') as cleanup:
            with self.assertRaises(ValidationError): save_license(form, self.driver)
        cleanup.assert_called_once_with(['new-id'])
        self.license.refresh_from_db()
        self.assertEqual(self.license.license_class, 'C1')
        self.assertEqual(self.license.front_image_url, 'https://example.com/front.jpg')

    def test_rejected_profile_resubmission(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('frontend:driver-action', args=[self.driver.pk]), {'action': 'reject', 'version': revision(self.driver)})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'REJECTED')
        self.client.force_login(self.user)
        self.client.post(reverse('frontend:profile'), {**self.profile_payload(), 'address': 'Địa chỉ mới'})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'PENDING')

    def test_end_suspended_assignment_but_cannot_extend_or_create(self):
        self.user.is_active = False
        self.user.save()
        self.vehicle.status = 'INACTIVE'
        self.vehicle.save()
        end = timezone.now()
        payload = dict(driver=self.driver.pk, vehicle=self.vehicle.pk, start_at=self.assignment.start_at, end_at=end)
        form = AssignmentForm(payload, instance=self.assignment)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        for end_value in (end+timedelta(days=1), ''):
            form = AssignmentForm({**payload, 'end_at': end_value}, instance=self.assignment)
            self.assertFalse(form.is_valid())
        self.assertFalse(AssignmentForm(payload).is_valid())

    def test_expired_license_display_and_approval(self):
        self.license.status = 'ACTIVE'
        self.license.expiry_date = timezone.localdate()-timedelta(days=1)
        self.license.save()
        self.assertFalse(self.license.is_valid)
        self.assertEqual(self.license.effective_status, 'EXPIRED')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('frontend:license')), 'Expired')
        self.license.status = 'PENDING'
        self.license.save()
        self.client.force_login(self.admin)
        self.client.post(reverse('frontend:driver-action', args=[self.driver.pk]), {'action':'license-approve', 'version':revision(self.license)})
        self.license.refresh_from_db()
        self.assertEqual(self.license.status, 'PENDING')
