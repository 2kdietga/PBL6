from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from frontend.forms import AssignmentForm, VehicleForm
from .licensing import required_license_class, license_covers
from .models import VehicleType, Vehicle, DriverVehicleAssignment


class LicenseRulesTests(SimpleTestCase):
    def test_truck_boundaries_use_gross_design_mass(self):
        for mass, expected in [('3500', 'B'), ('3500.01', 'C1'), ('7500', 'C1'), ('7500.01', 'C')]:
            with self.subTest(mass=mass):
                self.assertEqual(required_license_class('TRUCK', Decimal(mass)), expected)
        for mass in (None, 0, -1):
            self.assertIsNone(required_license_class('TRUCK', mass))

    def test_passenger_boundaries_and_sleeper(self):
        for count, expected in [(8, 'B'), (9, 'D1'), (16, 'D1'), (17, 'D2'), (29, 'D2'), (30, 'D')]:
            self.assertEqual(required_license_class('BUS', passengers=count), expected)
            self.assertEqual(required_license_class('BUS', passengers=count, sleeper=True), 'D')
        self.assertIsNone(required_license_class('BUS', passengers=0))

    def test_class_entitlements(self):
        for held, required in [('C1', 'B'), ('C', 'C1'), ('D1', 'C'), ('D2', 'D1'), ('D', 'D2'), ('CE', 'C')]:
            self.assertTrue(license_covers(held, required))
        for held, required in [('B', 'C1'), ('C', 'D1'), ('D1', 'D2'), ('D2', 'D'), ('B2', 'B'), ('E', 'D'), ('', 'B')]:
            self.assertFalse(license_covers(held, required))


class AssignmentLicenseTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', role='ADMIN')
        user = User.objects.create_user('driver')
        self.driver = DriverProfile.objects.create(user=user, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        self.license = DriverLicense.objects.create(driver=self.driver, license_number='TEST',
            license_class='B', license_standard='VN_2025', status='ACTIVE', issued_date=date(2025, 1, 1),
            expiry_date=timezone.localdate()+timedelta(days=365),
            front_image_url='https://example.com/front.jpg', back_image_url='https://example.com/back.jpg')
        FaceProfile.objects.create(driver=self.driver, embedding=[1], face_image_url='https://example.com/face.jpg', approval_status='APPROVED')
        self.driver.refresh_from_db()
        self.driver.approval_status = 'APPROVED'
        self.driver.save()
        self.kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        self.vehicle = Vehicle.objects.create(vehicle_type=self.kind, license_plate='TEST',
            load_capacity=1000, gross_vehicle_weight=5000)
        self.payload = dict(driver=self.driver.pk, vehicle=self.vehicle.pk, start_at=timezone.now())
        self.client.force_login(self.admin)

    def test_web_blocks_insufficient_class_and_accepts_sufficient_class(self):
        url = reverse('frontend:create', args=['assignments'])
        response = self.client.post(url, self.payload)
        self.assertContains(response, 'yêu cầu GPLX hạng C1')
        self.assertFalse(DriverVehicleAssignment.objects.exists())
        self.license.license_class = 'C1'
        self.license.save()
        self.assertEqual(self.client.post(url, self.payload).status_code, 302)
        self.assertEqual(DriverVehicleAssignment.objects.count(), 1)

    def test_missing_specs_unknown_standard_and_expired_license_block(self):
        self.vehicle.gross_vehicle_weight = None
        self.vehicle.save()
        self.assertFalse(AssignmentForm(self.payload).is_valid())
        self.vehicle.gross_vehicle_weight = 2500
        self.vehicle.save()
        self.license.license_standard = ''
        self.license.save()
        self.assertFalse(AssignmentForm(self.payload).is_valid())
        self.license.license_standard = 'VN_2025'
        self.license.expiry_date = timezone.localdate()
        self.license.save()
        self.assertFalse(AssignmentForm(self.payload).is_valid())

    def test_ending_is_allowed_but_extension_rechecks_class(self):
        assignment = DriverVehicleAssignment.objects.create(**{
            'driver': self.driver, 'vehicle': self.vehicle, 'start_at': self.payload['start_at'],
            'end_at': timezone.now()+timedelta(days=1)})
        self.assertTrue(AssignmentForm({**self.payload, 'end_at': timezone.now()+timedelta(hours=1)}, instance=assignment).is_valid())
        assignment.refresh_from_db()
        self.assertFalse(AssignmentForm({**self.payload, 'end_at': timezone.now()+timedelta(days=2)}, instance=assignment).is_valid())

    def test_vehicle_form_requires_mass_and_ignores_submitted_grade(self):
        payload = dict(license_plate='NEW', vehicle_type=self.kind.pk, load_capacity=1000, status='ACTIVE')
        form = VehicleForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn('gross_vehicle_weight', form.errors)
        form = VehicleForm({**payload, 'gross_vehicle_weight': 8000, 'required_license': 'B'})
        self.assertTrue(form.is_valid(), form.errors)
        vehicle = form.save()
        self.assertEqual(vehicle.required_license_class, 'C')
        self.assertContains(self.client.get(reverse('frontend:vehicles')), 'GPLX yêu cầu')
        form = VehicleForm({**payload, 'gross_vehicle_weight': 3000}, instance=vehicle)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().required_license_class, 'B')

    def test_truck_license_does_not_cover_bus_and_sleeper_requires_d(self):
        bus = VehicleType.objects.create(name='Bus', category='BUS')
        self.vehicle.vehicle_type = bus
        self.vehicle.passenger_capacity = 16
        self.vehicle.save()
        self.license.license_class = 'C'
        self.license.save()
        self.assertFalse(AssignmentForm(self.payload).is_valid())
        self.license.license_class = 'D1'
        self.license.save()
        self.assertTrue(AssignmentForm(self.payload).is_valid())
        self.vehicle.is_sleeper = True
        self.vehicle.save()
        self.assertFalse(AssignmentForm(self.payload).is_valid())
