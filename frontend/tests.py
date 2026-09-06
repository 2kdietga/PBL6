from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, DriverProfile, DriverLicense
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment, Device
from driving.models import DrivingSession


class DynamicPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('manager', password='Secret123!', role='ADMIN')
        cls.user = User.objects.create_user('driver', password='Secret123!')
        cls.other = User.objects.create_user('other', password='Secret123!')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Nguyễn Minh', date_of_birth=date(1990, 1, 1), phone='0905000000', address='Đà Nẵng', approval_status='APPROVED')
        cls.other_driver = DriverProfile.objects.create(user=cls.other, full_name='Tài xế khác', date_of_birth=date(1990, 1, 1), phone='0905111111', address='Huế', approval_status='APPROVED')
        cls.kind = VehicleType.objects.create(name='Xe tải', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(license_plate='43C-11111', vehicle_type=cls.kind, load_capacity=5000)
        cls.other_vehicle = Vehicle.objects.create(license_plate='43C-22222', vehicle_type=cls.kind, load_capacity=5000)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle, start_at=timezone.now()-timedelta(days=1))
        cls.other_assignment = DriverVehicleAssignment.objects.create(driver=cls.other_driver, vehicle=cls.other_vehicle, start_at=timezone.now()-timedelta(days=1))
        cls.session = DrivingSession.objects.create(assignment=cls.assignment, started_at=timezone.now())
        DrivingSession.objects.create(assignment=cls.other_assignment, started_at=timezone.now())

    def url(self, name, *args):
        return reverse('frontend:' + name, args=args)

    def test_anonymous_redirected_and_login_works(self):
        self.assertRedirects(self.client.get(self.url('vehicles')), self.url('login')+'?next=/vehicles/')
        response = self.client.post(self.url('login'), {'username': 'driver', 'password': 'Secret123!'})
        self.assertRedirects(response, self.url('dashboard'))
        self.assertNotContains(self.client.get(self.url('dashboard')), '/static/app.js')

    def test_registration_cannot_assign_admin_role(self):
        response = self.client.post(self.url('register'), {'username':'newdriver', 'email':'new@example.com', 'password1':'SecureLong123!', 'password2':'SecureLong123!', 'role':'ADMIN', 'is_staff':'true'})
        self.assertRedirects(response, self.url('profile'))
        user = User.objects.get(username='newdriver')
        self.assertEqual(user.role, 'USER')
        self.assertFalse(user.is_staff)

    def test_admin_pages_render_real_database(self):
        self.client.force_login(self.admin)
        for name in ['dashboard','drivers','vehicles','assignments','sessions','devices','catalogs']:
            with self.subTest(name=name): self.assertEqual(self.client.get(self.url(name)).status_code, 200)
        self.assertContains(self.client.get(self.url('vehicles')), '43C-11111')
        for key in ['vehicles','assignments','devices','catalogs']:
            self.assertEqual(self.client.get(self.url('create', key)).status_code, 200)
        self.assertEqual(self.client.get(self.url('driver-detail', self.driver.pk)).status_code, 200)

    def test_driver_scope_and_admin_endpoints(self):
        self.client.force_login(self.user)
        for name in ['dashboard','vehicles','sessions','profile','license']:
            self.assertEqual(self.client.get(self.url(name)).status_code, 200)
        for name in ['drivers','assignments','devices','catalogs']:
            self.assertEqual(self.client.get(self.url(name)).status_code, 403)
        response = self.client.get(self.url('vehicles'))
        self.assertContains(response, '43C-11111')
        self.assertNotContains(response, '43C-22222')
        self.assertNotContains(self.client.get(self.url('sessions')), 'Tài xế khác')
        self.assertEqual(self.client.post(self.url('create', 'vehicles'), {}).status_code, 403)
        self.assertEqual(self.client.post(self.url('driver-action', self.other_driver.pk), {'action':'approve'}).status_code, 403)

    def test_expired_assignment_does_not_borrow_other_driver_validity(self):
        self.assignment.end_at = timezone.now()-timedelta(hours=1)
        self.assignment.save()
        DriverVehicleAssignment.objects.create(driver=self.other_driver, vehicle=self.vehicle, start_at=timezone.now()-timedelta(hours=1))
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(self.url('vehicles')), '43C-11111')
        self.assertContains(self.client.get(self.url('sessions')), '43C-11111')

    def test_vehicle_creation_validation_and_persistence(self):
        self.client.force_login(self.admin)
        payload = dict(license_plate='43C-33333', vehicle_type=self.kind.pk, status='ACTIVE', load_capacity='6000')
        self.assertRedirects(self.client.post(self.url('create', 'vehicles'), payload), self.url('vehicles'))
        self.assertTrue(Vehicle.objects.filter(license_plate='43C-33333').exists())
        self.assertEqual(self.client.post(self.url('create', 'vehicles'), payload).status_code, 200)
        self.assertEqual(Vehicle.objects.filter(license_plate='43C-33333').count(), 1)
        payload.update(license_plate='invalid', load_capacity='0')
        self.client.post(self.url('create', 'vehicles'), payload)
        self.assertFalse(Vehicle.objects.filter(license_plate='invalid').exists())

    def test_profile_updates_only_current_driver_and_reapproval(self):
        self.client.force_login(self.user)
        payload = dict(full_name=self.driver.full_name, date_of_birth='1990-01-01', phone='0905222222', address='Đà Nẵng', user=self.other.pk, approval_status='APPROVED')
        self.client.post(self.url('profile'), payload)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'APPROVED')
        payload['full_name'] = 'Tên mới'
        self.client.post(self.url('profile'), payload)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.assertEqual(self.driver.user_id, self.user.pk)

    def test_first_profile_and_license_workflow(self):
        user = User.objects.create_user('fresh', password='Secret123!')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url('license')), self.url('profile'))
        self.client.post(self.url('profile'), dict(full_name='Tài xế mới', date_of_birth='1990-02-02', phone='0905000001', address='Đà Nẵng'))
        driver = DriverProfile.objects.get(user=user)
        self.assertEqual(driver.approval_status, 'PENDING')
        payload = dict(license_number='UNIQUE123', license_class='C', issued_date='2025-01-01', expiry_date='2030-01-01', front_image_url='https://example.com/front.jpg', back_image_url='https://example.com/back.jpg')
        self.assertRedirects(self.client.post(self.url('license'), payload), self.url('license'))
        obj = DriverLicense.objects.get(driver=driver)
        self.client.force_login(self.admin)
        self.client.post(self.url('driver-action', driver.pk), {'action':'license-approve'})
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'ACTIVE')
        self.client.force_login(user)
        payload['license_class'] = 'D'
        self.client.post(self.url('license'), payload)
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'PENDING')
        self.assertEqual(DriverLicense.objects.filter(driver=driver).count(), 1)

    def test_csrf_and_post_only_actions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url('driver-action', self.driver.pk), {'action':'disable'}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('driver-action', self.driver.pk)).status_code, 405)
        self.assertEqual(self.client.get(self.url('logout')).status_code, 405)

    def test_disabled_account_cannot_login(self):
        self.client.force_login(self.admin)
        self.client.post(self.url('driver-action', self.driver.pk), {'action':'disable'})
        self.client.logout()
        self.client.post(self.url('login'), {'username':'driver', 'password':'Secret123!'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_no_session_creation_or_edit_from_web(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url('create', 'sessions'), {}).status_code, 403)
        self.assertEqual(self.client.post(self.url('edit', 'sessions', self.session.pk), {}).status_code, 403)
        self.assertEqual(DrivingSession.objects.count(), 2)

    def test_search_pagination_and_escaping(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(self.url('vehicles'), {'q':'22222'}), '43C-11111')
        self.driver.full_name = '<script>alert(1)</script>'
        self.driver.save()
        self.assertContains(self.client.get(self.url('drivers')), '&lt;script&gt;')
        for index in range(22): VehicleType.objects.create(name=f'Type {index}', category='BUS')
        response = self.client.get(self.url('catalogs'), {'page':'2'})
        self.assertEqual(response.context['pagination'].number, 2)

    def test_invalid_assignment_and_duplicate_device(self):
        self.client.force_login(self.admin)
        payload = dict(driver=self.driver.pk, vehicle=self.vehicle.pk, start_at='2026-09-07T08:00', end_at='2026-09-06T08:00')
        self.client.post(self.url('create', 'assignments'), payload)
        self.assertEqual(DriverVehicleAssignment.objects.count(), 2)
        payload = dict(device_code='PI-1', name='Camera', vehicle=self.vehicle.pk, status='OFFLINE')
        self.assertRedirects(self.client.post(self.url('create', 'devices'), payload), self.url('devices'))
        payload['device_code'] = 'PI-2'
        self.client.post(self.url('create', 'devices'), payload)
        self.assertEqual(Device.objects.count(), 1)
