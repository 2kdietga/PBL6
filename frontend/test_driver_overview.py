from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DriverProfile
from driving.models import DrivingSession
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment
from violations.models import Appeal, Violation, ViolationType
from .driver_overview import driver_overview


class DriverOverviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.admin = User.objects.create_user('manager', role='ADMIN')
        cls.user = User.objects.create_user('driver')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Test driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='OVERVIEW-1', load_capacity=1000)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=cls.now-timedelta(days=100))
        cls.old = DrivingSession.objects.create(assignment=cls.assignment, status='ENDED',
            started_at=cls.now-timedelta(days=40, hours=2), ended_at=cls.now-timedelta(days=40))
        cls.recent = DrivingSession.objects.create(assignment=cls.assignment, status='ENDED',
            started_at=cls.now-timedelta(hours=4), ended_at=cls.now-timedelta(hours=1))
        cls.active = DrivingSession.objects.create(assignment=cls.assignment, started_at=cls.now-timedelta(minutes=30))
        cls.kind = ViolationType.objects.create(code='PHONE', name='Phone')
        for status in Violation.Status.values:
            violation = Violation.objects.create(session=cls.recent, violation_type=cls.kind,
                severity='HIGH', status=status, detected_at=cls.now-timedelta(hours=2))
            if status == 'REVOKED':
                Appeal.objects.create(violation=violation, content='Reviewed', status='APPROVED')
        Violation.objects.create(session=cls.old, violation_type=cls.kind, severity='LOW', status='APPROVED',
            detected_at=cls.now-timedelta(days=40))

    def test_counts_duration_and_statuses_do_not_multiply_across_relations(self):
        overview = driver_overview(self.driver, now=self.now)
        self.assertEqual(overview['sessions']['total'], 3)
        self.assertEqual(overview['sessions']['ended'], 2)
        self.assertEqual(overview['sessions']['started'], 1)
        self.assertEqual(overview['sessions']['vehicles'], 1)
        self.assertEqual(overview['sessions']['duration_label'], '5 giờ 0 phút')
        self.assertEqual(overview['violations']['APPROVED'], 2)
        self.assertEqual(overview['violations']['REVOKED'], 1)
        self.assertEqual(overview['high_severity'], 1)
        self.assertEqual(overview['top_types'][0]['total'], 2)
        self.assertEqual(overview['appeals']['APPROVED'], 1)

    def test_period_applies_to_events_but_not_current_assignment(self):
        overview = driver_overview(self.driver, '30', self.now)
        self.assertEqual(overview['sessions']['total'], 2)
        self.assertEqual(overview['sessions']['duration_label'], '3 giờ 0 phút')
        self.assertEqual(overview['violations']['APPROVED'], 1)
        self.assertEqual(len(overview['current_assignments']), 1)
        self.assertEqual(driver_overview(self.driver, 'bad', self.now)['period'], 'all')

    def test_assignment_boundaries_and_empty_driver_are_isolated(self):
        user = User.objects.create_user('empty')
        driver = DriverProfile.objects.create(user=user, full_name='Empty', date_of_birth=date(1990, 1, 1), phone='123', address='City')
        overview = driver_overview(driver, now=self.now)
        self.assertEqual(overview['sessions']['total'], 0)
        self.assertEqual(overview['violations']['total'], 0)
        self.assertEqual(overview['sessions']['duration_label'], '0 giờ 0 phút')
        self.assertEqual(overview['current_assignments'], [])
        DriverVehicleAssignment.objects.filter(pk=self.assignment.pk).update(end_at=self.now)
        self.assertEqual(driver_overview(self.driver, now=self.now)['current_assignments'], [])
        DriverVehicleAssignment.objects.create(driver=driver, vehicle=self.vehicle, start_at=self.now+timedelta(days=1))
        overview = driver_overview(driver, now=self.now)
        self.assertEqual(overview['assignment_counts']['upcoming'], 1)
        self.assertEqual(overview['current_assignments'], [])

    def test_page_renders_tables_and_preserves_admin_only_access(self):
        url = reverse('frontend:driver-detail', args=[self.driver.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(url, {'period': '30'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tổng quan hoạt động')
        self.assertContains(response, 'OVERVIEW-1')
        self.assertContains(response, '3 giờ 0 phút')
        self.assertNotContains(response, 'Hồ sơ tài xế')
        self.assertContains(response, 'value="30" selected')
        profile = self.client.get(url, {'tab': 'profile'})
        self.assertContains(profile, 'Hồ sơ tài xế')
        self.assertNotContains(profile, 'driver-metrics')
        for tab in ('sessions', 'violations'):
            response = self.client.get(url, {'tab': tab, 'period': '30'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<table>')
            self.assertNotContains(response, 'Hồ sơ tài xế')
