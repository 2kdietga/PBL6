from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.concurrency import revision
from accounts.models import User, DriverProfile
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment
from .models import DrivingShift, DrivingSession, ShiftAudit
from .shift_forms import ShiftForm
from .shift_services import attendance, save_shift, shift_action, select_shift, monthly_summary
from .device_protocol import DeviceAPIError


class ShiftTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now().replace(microsecond=0)
        cls.admin = User.objects.create_user('manager', role='ADMIN')
        cls.user = User.objects.create_user('driver')
        cls.other = User.objects.create_user('other')
        cls.driver = DriverProfile.objects.create(user=cls.user, full_name='Driver', date_of_birth=date(1990,1,1), phone='123', address='City')
        cls.other_driver = DriverProfile.objects.create(user=cls.other, full_name='Other', date_of_birth=date(1990,1,1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='SHIFT-1', gross_vehicle_weight=3000)
        cls.vehicle2 = Vehicle.objects.create(vehicle_type=kind, license_plate='SHIFT-2', gross_vehicle_weight=3000)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=cls.driver, vehicle=cls.vehicle,
            start_at=cls.now-timedelta(days=30), end_at=cls.now+timedelta(days=30))

    def create(self, **kwargs):
        values = dict(assignment=self.assignment, start_at=self.now+timedelta(hours=1), end_at=self.now+timedelta(hours=5))
        values.update(kwargs)
        return DrivingShift.objects.create(**values)

    def payload(self, **kwargs):
        values = dict(assignment=self.assignment.pk, start_at=self.now+timedelta(hours=1),
            end_at=self.now+timedelta(hours=5), early_minutes=15, grace_minutes=5, note='Route A')
        values.update(kwargs)
        return values

    def test_create_edit_audit_and_stale_form(self):
        form = ShiftForm(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        shift = save_shift(form, self.admin)
        self.assertEqual(shift.audits.count(), 1)
        form = ShiftForm(self.payload(note='Changed', reason='New route', version=revision(shift)), instance=shift)
        self.assertTrue(form.is_valid(), form.errors)
        shift = save_shift(form, self.admin)
        self.assertEqual(shift.audits.count(), 2)
        with self.assertRaises(ValidationError):
            shift_action(shift.pk, {'version': 'stale', 'action': 'cancel', 'response': 'test'}, self.admin)

    def test_overlap_driver_and_vehicle_and_assignment_boundaries(self):
        self.create()
        driver_overlap = DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle2, start_at=self.now)
        vehicle_overlap = DriverVehicleAssignment.objects.create(driver=self.other_driver, vehicle=self.vehicle, start_at=self.now)
        for assignment in (self.assignment, driver_overlap, vehicle_overlap):
            form = ShiftForm(self.payload(assignment=assignment.pk))
            self.assertFalse(form.is_valid())
        self.assertFalse(ShiftForm(self.payload(start_at=self.now+timedelta(days=31), end_at=self.now+timedelta(days=32))).is_valid())
        form = ShiftForm(self.payload(start_at=self.now+timedelta(hours=5), end_at=self.now+timedelta(hours=6)))
        self.assertTrue(form.is_valid(), form.errors)

    def test_early_window_and_current_shift_precedence(self):
        shift = self.create()
        with self.assertRaises(DeviceAPIError) as caught:
            select_shift(self.assignment, shift.start_at-timedelta(minutes=16))
        self.assertEqual(caught.exception.code, 'NO_SCHEDULED_SHIFT')
        self.assertEqual(select_shift(self.assignment, shift.start_at-timedelta(minutes=15)).pk, shift.pk)
        next_shift = self.create(start_at=shift.end_at, end_at=shift.end_at+timedelta(hours=2))
        self.assertEqual(select_shift(self.assignment, shift.end_at-timedelta(minutes=5)).pk, shift.pk)
        self.assertEqual(select_shift(self.assignment, shift.end_at).pk, next_shift.pk)

    def test_multiple_sessions_use_first_start_and_exclude_open_from_review(self):
        shift = self.create(start_at=self.now-timedelta(hours=5), end_at=self.now-timedelta(hours=1))
        DrivingSession.objects.create(assignment=self.assignment, shift=shift, status='ENDED',
            started_at=shift.start_at+timedelta(minutes=5), ended_at=shift.start_at+timedelta(hours=1))
        session = DrivingSession.objects.create(assignment=self.assignment, shift=shift, started_at=shift.start_at+timedelta(hours=2))
        actual = attendance(shift, self.now)
        self.assertEqual(actual['punctuality'], 'ON_TIME')
        self.assertFalse(actual['can_review'])
        session.status, session.ended_at = 'ENDED', shift.end_at
        session.save()
        self.assertTrue(attendance(shift, self.now)['can_review'])

    def test_explanation_review_and_month_report(self):
        shift = self.create(start_at=self.now-timedelta(hours=5), end_at=self.now-timedelta(hours=1))
        shift = shift_action(shift.pk, {'version': revision(shift), 'action': 'explain', 'explanation': 'Device failed'}, self.user)
        shift = shift_action(shift.pk, {'version': revision(shift), 'action': 'review', 'decision': 'EXCUSED', 'response': 'Confirmed device failure'}, self.admin)
        self.assertEqual(shift.decision, 'EXCUSED')
        report = monthly_summary(self.driver, timezone.localtime(shift.start_at).date())
        self.assertEqual(report['EXCUSED'], 1)
        self.assertIsNone(report['rate'])
        self.assertEqual(shift.audits.count(), 2)

    def test_absence_is_pending_until_admin_reviews(self):
        shift = self.create(start_at=self.now-timedelta(hours=3), end_at=self.now-timedelta(hours=1))
        self.assertIn('chờ xác nhận', attendance(shift)['label'])
        with self.assertRaises(ValidationError):
            shift_action(shift.pk, {'version': revision(shift), 'action': 'review', 'decision': 'ON_TIME', 'response': 'Wrong'}, self.admin)
        shift_action(shift.pk, {'version': revision(shift), 'action': 'review', 'decision': 'ABSENT', 'response': 'Confirmed absence'}, self.admin)
        report = monthly_summary(self.driver, timezone.localtime(shift.start_at).date())
        self.assertEqual(report['ABSENT'], 1)
        self.assertEqual(report['rate'], 0)

    def test_permission_csrf_and_pages(self):
        shift = self.create()
        url = reverse('frontend:shift-detail', args=[shift.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('frontend:shifts')), 'SHIFT-1')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('frontend:shift-create')).status_code, 403)
        self.assertContains(self.client.get(url), 'Tôi đã nhận lịch')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse('frontend:shift-action', args=[shift.pk]), {}).status_code, 403)
        self.client.force_login(self.admin)
        for name in ('shifts', 'shift-create', 'shift-report'):
            self.assertEqual(self.client.get(reverse('frontend:'+name)).status_code, 200)
        self.assertContains(self.client.get(url), 'Sửa lịch')

    def test_cancellation_and_shortening_assignment(self):
        shift = self.create()
        self.assignment.end_at = shift.start_at
        with self.assertRaises(ValidationError):
            self.assignment.save()
        shift_action(shift.pk, {'version': revision(shift), 'action': 'cancel', 'response': 'Route cancelled'}, self.admin)
        self.assignment.save()
        with self.assertRaises(DeviceAPIError):
            select_shift(self.assignment, shift.start_at)

    def test_schedule_cannot_be_rewritten_after_start(self):
        shift = self.create(start_at=self.now-timedelta(minutes=1))
        form = ShiftForm(self.payload(version=revision(shift), reason='Change time'), instance=shift)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(ValidationError):
            save_shift(form, self.admin)

    def test_late_minutes_and_finalized_rate(self):
        shift = self.create(start_at=self.now-timedelta(hours=4), end_at=self.now-timedelta(hours=1))
        DrivingSession.objects.create(assignment=self.assignment, shift=shift, status='ENDED',
            started_at=shift.start_at+timedelta(minutes=15), ended_at=shift.end_at)
        actual = attendance(shift, self.now)
        self.assertEqual(actual['late_minutes'], 15)
        self.assertEqual(actual['punctuality'], 'LATE')
        shift_action(shift.pk, {'version': revision(shift), 'action': 'review', 'decision': 'LATE', 'response': 'Reviewed'}, self.admin)
        stats = monthly_summary(self.driver, timezone.localtime(shift.start_at).date())
        self.assertEqual(stats['late_minutes'], 15)
        self.assertEqual(stats['LATE'], 1)
        self.assertEqual(stats['assessed'], 1)

    def test_overlap_rechecked_after_form_validation(self):
        form = ShiftForm(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        self.create()
        with self.assertRaises(ValidationError):
            save_shift(form, self.admin)
        self.assertEqual(DrivingShift.objects.count(), 1)

    def test_overnight_shift_renders_on_both_days(self):
        start = timezone.localtime(self.now).replace(hour=23, minute=0)
        shift = self.create(start_at=start, end_at=start+timedelta(hours=3))
        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:shifts'), {'week': start.date().isoformat()})
        matching = [d for d in response.context['days'] if any(i['shift'].pk == shift.pk for i in d['items'])]
        self.assertEqual(len(matching), 1 if start.weekday() == 6 else 2)
        self.assertEqual(self.client.get(reverse('frontend:shift-report')).status_code, 200)

    def test_cancelled_and_pending_not_in_rate(self):
        self.create(start_at=self.now-timedelta(hours=4), end_at=self.now-timedelta(hours=3), cancelled=True)
        pending = self.create(start_at=self.now-timedelta(hours=2), end_at=self.now-timedelta(hours=1))
        stats = monthly_summary(self.driver, timezone.localtime(pending.start_at).date())
        self.assertEqual(stats['pending'], 1)
        self.assertEqual(stats['assessed'], 0)
        self.assertIsNone(stats['rate'])
