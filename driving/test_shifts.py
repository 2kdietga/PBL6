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
from .shift_forms import ShiftForm, ShiftCorrectionForm
from .shift_services import correct_shift
from .shift_services import attendance, save_shift, shift_action, select_shift, monthly_summary, monthly_summaries
from .device_protocol import DeviceAPIError


class ShiftTests(TestCase):
    def second_assignment(self):
        return DriverVehicleAssignment.objects.create(driver=self.other_driver, vehicle=self.vehicle,
            start_at=self.assignment.start_at, end_at=self.assignment.end_at)

    def test_shared_shift_form_and_driver_conflicts(self):
        second = self.second_assignment()
        form = ShiftForm(self.payload(second_assignment=second.pk))
        self.assertTrue(form.is_valid(), form.errors)
        shift = save_shift(form, self.admin)
        self.assertEqual(shift.second_assignment_id, second.pk)
        self.assertFalse(ShiftForm(self.payload(second_assignment=self.assignment.pk)).is_valid())
        elsewhere = DriverVehicleAssignment.objects.create(driver=self.other_driver, vehicle=self.vehicle2, start_at=self.now)
        self.assertFalse(ShiftForm(self.payload(assignment=elsewhere.pk)).is_valid())
        shift.cancelled = True
        shift.save()
        self.assertFalse(ShiftForm(self.payload(second_assignment=elsewhere.pk)).is_valid())
        second.end_at = self.now+timedelta(hours=2)
        second.save()
        self.assertFalse(ShiftForm(self.payload(second_assignment=second.pk)).is_valid())

    def test_shared_shift_access_acknowledgements_and_explanations_are_independent(self):
        second = self.second_assignment()
        shift = self.create(second_assignment=second)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('frontend:shift-detail', args=[shift.pk])), 'Other')
        calendar = self.client.get(reverse('frontend:shifts'), {'week': timezone.localdate(shift.start_at).isoformat()})
        self.assertContains(calendar, reverse('frontend:shift-detail', args=[shift.pk]))
        for user in (self.user, self.other):
            shift = shift_action(shift.pk, dict(version=revision(shift), action='acknowledge'), user)
            shift = shift_action(shift.pk, dict(version=revision(shift), action='explain', explanation=user.username), user)
        self.assertIsNotNone(shift.acknowledged_at)
        self.assertIsNotNone(shift.second_acknowledged_at)
        self.assertEqual(shift.explanation, self.user.username)
        self.assertEqual(shift.second_explanation, self.other.username)
        outsider = User.objects.create_user('outsider')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('frontend:shift-detail', args=[shift.pk])).status_code, 404)

    def test_shared_report_excludes_individual_lateness_and_counts_own_sessions(self):
        second = self.second_assignment()
        shift = self.create(second_assignment=second, start_at=self.now-timedelta(hours=4),
                            end_at=self.now-timedelta(hours=1), decision='LATE')
        DrivingSession.objects.create(assignment=self.assignment, shift=shift, status='ENDED',
            started_at=shift.start_at+timedelta(minutes=10), ended_at=shift.start_at+timedelta(hours=1))
        reports = monthly_summaries([self.driver.pk, self.other_driver.pk], timezone.localdate(shift.start_at))
        for data in reports.values():
            self.assertEqual(data['shared'], 1)
            self.assertEqual(data['total'], 1)
            self.assertEqual(data['due'], 1)
            self.assertEqual(data['LATE'], 0)
            self.assertEqual(data['ABSENT'], 0)
            self.assertIsNone(data['rate'])
        self.assertEqual(reports[self.driver.pk]['performed'], 1)
        self.assertEqual(reports[self.other_driver.pk]['performed'], 0)
        self.assertEqual(monthly_summary(self.other_driver, timezone.localdate(shift.start_at))['shared'], 1)

    def test_second_assignment_cannot_be_shortened_or_reassigned(self):
        second = self.second_assignment()
        shift = self.create(second_assignment=second)
        second.end_at = shift.end_at-timedelta(minutes=1)
        with self.assertRaises(ValidationError):
            second.save()
        second.refresh_from_db()
        second.vehicle = self.vehicle2
        with self.assertRaises(ValidationError):
            second.save()

    def test_shared_correction_preserves_both_drivers_and_sessions(self):
        second = self.second_assignment()
        old = self.create(second_assignment=second, start_at=self.now-timedelta(hours=1))
        DrivingSession.objects.create(assignment=second, shift=old, status='ENDED',
            started_at=old.start_at, ended_at=self.now)
        form = self.correction(old, second_assignment=second.pk)
        self.assertTrue(form.is_valid(), form.errors)
        new = correct_shift(old.pk, form, self.admin)
        self.assertEqual(new.second_assignment_id, second.pk)
        self.assertEqual(old.sessions.get().assignment_id, second.pk)

    def correction(self, old, **kwargs):
        return ShiftCorrectionForm(self.payload(reason='Admin phân nhầm', version=revision(old), **kwargs), original=old)

    def test_correction_preserves_sessions_and_excludes_old_from_report(self):
        old = self.create(start_at=self.now-timedelta(hours=2))
        session = DrivingSession.objects.create(assignment=self.assignment, shift=old, status='ENDED',
            started_at=old.start_at, ended_at=self.now-timedelta(hours=1))
        form = self.correction(old)
        self.assertTrue(form.is_valid(), form.errors)
        new = correct_shift(old.pk, form, self.admin)
        old.refresh_from_db()
        session.refresh_from_db()
        self.assertTrue(old.cancelled)
        self.assertEqual(new.replaces_id, old.pk)
        self.assertEqual(session.shift_id, old.pk)
        self.assertEqual(session.ended_at, self.now-timedelta(hours=1))
        self.assertEqual(old.audits.count(), 1)
        self.assertEqual(new.audits.count(), 1)
        self.assertIn('Nhầm phân công', attendance(old)['label'])
        self.assertEqual(monthly_summary(self.driver, timezone.localdate(new.start_at))['total'], 1)
        with self.assertRaises(ValidationError):
            correct_shift(old.pk, form, self.admin)

    def test_correction_blocks_open_session_and_missing_reason(self):
        old = self.create(start_at=self.now-timedelta(hours=2))
        DrivingSession.objects.create(assignment=self.assignment, shift=old, started_at=old.start_at)
        form = self.correction(old)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(ValidationError):
            correct_shift(old.pk, form, self.admin)
        old.refresh_from_db()
        self.assertFalse(old.cancelled)
        self.assertFalse(ShiftCorrectionForm(self.payload(version=revision(old)), original=old).is_valid())

    def test_correction_permissions_stale_form_conflict_and_rollback(self):
        old = self.create(start_at=self.now-timedelta(hours=2))
        form = self.correction(old)
        self.assertTrue(form.is_valid(), form.errors)
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            correct_shift(old.pk, form, self.user)
        form.cleaned_data['version'] = 'stale'
        with self.assertRaises(ValidationError):
            correct_shift(old.pk, form, self.admin)
        form.cleaned_data['version'] = revision(old)
        self.create(start_at=self.now+timedelta(hours=2), end_at=self.now+timedelta(hours=3))
        with self.assertRaises(ValidationError):
            correct_shift(old.pk, form, self.admin)
        old.refresh_from_db()
        self.assertFalse(old.cancelled)
        self.assertEqual(old.audits.count(), 0)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('frontend:shift-correct', args=[old.pk])).status_code, 403)

    def test_correction_view_changes_assignment(self):
        old = self.create(start_at=self.now-timedelta(hours=2))
        target = DriverVehicleAssignment.objects.create(driver=self.other_driver, vehicle=self.vehicle2, start_at=self.now)
        self.client.force_login(self.admin)
        detail = self.client.get(reverse('frontend:shift-detail', args=[old.pk]))
        self.assertContains(detail, 'Điều chỉnh lịch do nhầm phân công')
        response = self.client.post(reverse('frontend:shift-correct', args=[old.pk]),
            self.payload(assignment=target.pk, reason='Nhầm tài xế', version=revision(old)))
        self.assertEqual(response.status_code, 302)
        new = DrivingShift.objects.get(replaces=old)
        self.assertEqual(new.assignment_id, target.pk)
        self.assertContains(self.client.get(response.url), 'Ca thay thế cho ca')

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

    def test_assignment_choices_hide_expired_but_keep_future_and_historical_edit(self):
        expired = DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle,
            start_at=self.now-timedelta(days=90), end_at=self.now-timedelta(days=60))
        boundary = DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle,
            start_at=self.now-timedelta(days=1), end_at=self.now)
        future = DriverVehicleAssignment.objects.create(driver=self.driver, vehicle=self.vehicle,
            start_at=self.now+timedelta(days=40))
        with patch('driving.shift_forms.timezone.now', return_value=self.now):
            form = ShiftForm()
        ids = set(form.fields['assignment'].queryset.values_list('pk', flat=True))
        self.assertEqual(ids, {self.assignment.pk, future.pk})
        label = form.fields['assignment'].label_from_instance(future)
        self.assertIn(self.vehicle.license_plate, label)
        self.assertIn(timezone.localtime(future.start_at).strftime('%d/%m/%Y %H:%M'), label)
        self.assertIn('Không thời hạn', label)
        invalid = ShiftForm(self.payload(assignment=expired.pk))
        self.assertFalse(invalid.is_valid())
        self.assertIn('assignment', invalid.errors)
        historical = self.create(assignment=expired, start_at=expired.start_at, end_at=expired.end_at)
        edit_form = ShiftForm(instance=historical)
        self.assertEqual(list(edit_form.fields['assignment'].queryset), [expired])
        self.assertTrue(edit_form.fields['assignment'].disabled)

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

    def test_month_report_query_count_stays_bounded_for_twenty_drivers(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        driver_ids = []
        for index in range(20):
            user = User.objects.create_user(f'perf-{index}')
            driver = DriverProfile.objects.create(user=user, full_name=f'A-{index}',
                date_of_birth=date(1990,1,1), phone='123', address='City')
            driver_ids.append(driver.pk)
            assignment = DriverVehicleAssignment.objects.create(driver=driver, vehicle=self.vehicle,
                start_at=self.now-timedelta(days=1))
            self.create(assignment=assignment, start_at=self.now, end_at=self.now+timedelta(hours=1))
        with self.assertNumQueries(1):
            summary = monthly_summaries(driver_ids, timezone.localdate())
        self.assertEqual(len(summary), 20)
        self.assertTrue(all(stats['total'] == 1 for stats in summary.values()))
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse('frontend:shift-report'))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured), 6)

    def test_invalid_report_month_and_filter_do_not_crash(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('frontend:shift-report'), {'month':'9999-12', 'driver':'9'*100})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['month'], timezone.localdate().replace(day=1))
