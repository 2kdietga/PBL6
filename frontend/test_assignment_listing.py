from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DriverProfile
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment


class AssignmentListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.admin = User.objects.create_user('manager', role='ADMIN')
        cls.user = User.objects.create_user('driver')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Driver A', date_of_birth=date(1990,1,1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='CAR-A', load_capacity=1000)
        cls.old = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=cls.now-timedelta(days=90), end_at=cls.now-timedelta(days=60))
        cls.active = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=cls.now-timedelta(days=1), end_at=cls.now+timedelta(days=1))
        cls.future = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=cls.now+timedelta(days=2))

    def test_default_tabs_filters_and_access(self):
        url = reverse('frontend:assignments')
        self.client.force_login(self.admin)
        with patch('frontend.assignment_views.timezone.now', return_value=self.now):
            for status, expected in ((None,[self.active]),('upcoming',[self.future]),('ended',[self.old])):
                response = self.client.get(url, {'status':status} if status else {})
                self.assertEqual(list(response.context['pagination']), expected)
            response = self.client.get(url, {'status':'all', 'driver':self.driver.pk, 'vehicle':self.vehicle.pk})
            self.assertEqual(response.context['pagination'].paginator.count, 3)
            self.assertContains(response, 'Không thời hạn')
            self.assertIn('driver=', response.context['pagination_query'])
            self.assertEqual(self.client.get(url, {'status':'invalid'}).context['selected_status'], 'active')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_boundaries(self):
        DriverVehicleAssignment.objects.filter(pk=self.active.pk).update(end_at=self.now)
        DriverVehicleAssignment.objects.filter(pk=self.future.pk).update(start_at=self.now)
        self.client.force_login(self.admin)
        with patch('frontend.assignment_views.timezone.now', return_value=self.now):
            response = self.client.get(reverse('frontend:assignments'))
            self.assertEqual(list(response.context['pagination']), [self.future])

    def test_overlap_rejected_but_adjacent_intervals_and_other_vehicles_allowed(self):
        overlap = DriverVehicleAssignment(driver=self.driver, vehicle=self.vehicle,
            start_at=self.now, end_at=self.now+timedelta(hours=1))
        with self.assertRaises(ValidationError):
            overlap.full_clean()
        overlap.start_at, overlap.end_at = self.active.end_at, self.future.start_at
        overlap.full_clean()
        vehicle = Vehicle.objects.create(vehicle_type=self.vehicle.vehicle_type, license_plate='CAR-B', load_capacity=1000)
        overlap.vehicle, overlap.start_at, overlap.end_at = vehicle, self.now, None
        overlap.full_clean()

    def test_legacy_overlap_can_be_shortened(self):
        legacy = DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle,
            start_at=self.now-timedelta(days=2))
        legacy.end_at = self.active.start_at
        legacy.full_clean()
