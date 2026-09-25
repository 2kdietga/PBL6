from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, DriverProfile
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment
from driving.models import DrivingSession


class EndAssignmentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', role='ADMIN')
        self.user = User.objects.create_user('driver')
        driver = DriverProfile.objects.create(user=self.user, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='Address')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        self.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='TEST')
        self.assignment = DriverVehicleAssignment.objects.create(driver=driver, vehicle=self.vehicle,
            start_at=timezone.now()-timedelta(days=1), end_at=timezone.now()+timedelta(days=7))
        self.url = reverse('frontend:assignment-end', args=[self.assignment.pk])
        self.edit_url = reverse('frontend:edit', args=['assignments', self.assignment.pk])
        self.client.force_login(self.admin)

    def test_end_early_preserves_history_and_revokes_vehicle_access(self):
        session = DrivingSession.objects.create(assignment=self.assignment, started_at=timezone.now())
        self.assertContains(self.client.get(self.edit_url), 'Kết thúc ngay')
        before = timezone.now()
        self.assertRedirects(self.client.post(self.url), reverse('frontend:assignments'))
        self.assignment.refresh_from_db()
        self.assertGreaterEqual(self.assignment.end_at, before)
        self.assertLessEqual(self.assignment.end_at, timezone.now())
        session.refresh_from_db()
        self.assertEqual(session.status, 'STARTED')
        self.assertEqual(session.assignment_id, self.assignment.pk)
        self.assertNotContains(self.client.get(self.edit_url), 'Kết thúc ngay')
        end = self.assignment.end_at
        self.client.post(self.url)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.end_at, end)
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('frontend:vehicles')), 'TEST')

    def test_open_ended_and_ineligible_driver_can_still_end(self):
        self.assignment.end_at = None
        self.assignment.save()
        self.user.is_active = False
        self.user.save()
        self.vehicle.status = 'INACTIVE'
        self.vehicle.save()
        self.client.post(self.url)
        self.assignment.refresh_from_db()
        self.assertIsNotNone(self.assignment.end_at)

    def test_future_assignment_is_not_changed(self):
        self.assignment.start_at = timezone.now()+timedelta(days=1)
        self.assignment.save()
        old_end = self.assignment.end_at
        self.assertNotContains(self.client.get(self.edit_url), 'Kết thúc ngay')
        self.client.post(self.url)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.end_at, old_end)

    def test_admin_post_and_csrf_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
