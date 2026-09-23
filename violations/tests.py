from datetime import date

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DriverProfile, User
from accounts.concurrency import revision
from driving.models import DrivingSession
from vehicles.models import DriverVehicleAssignment, Vehicle, VehicleType
from .models import Appeal, Evidence, Violation, ViolationType
from .models import ViolationReview


class ViolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('manager', role='ADMIN')
        cls.driver = User.objects.create_user('driver')
        cls.other = User.objects.create_user('other')
        profile = DriverProfile.objects.create(user=cls.driver, full_name='Nguyễn Minh', date_of_birth=date(1990, 1, 1), phone='0905000000', address='Đà Nẵng')
        vehicle_type = VehicleType.objects.create(name='Xe tải', category='TRUCK')
        vehicle = Vehicle.objects.create(license_plate='43C-11111', vehicle_type=vehicle_type, load_capacity=5000)
        assignment = DriverVehicleAssignment.objects.create(driver=profile, vehicle=vehicle, start_at=timezone.now())
        cls.session = DrivingSession.objects.create(assignment=assignment, started_at=timezone.now())
        cls.kind = ViolationType.objects.create(code='PHONE_USAGE', name='Sử dụng điện thoại')
        cls.violation = Violation.objects.create(session=cls.session, violation_type=cls.kind, severity='HIGH', detected_at=timezone.now())
        cls.evidence = Evidence.objects.create(violation=cls.violation, type='IMAGE', url='https://example.com/evidence.jpg', captured_at=timezone.now())

    def url(self, name, *args):
        return reverse('frontend:' + name, args=args)

    def review(self, **overrides):
        payload = dict(action='approve', violation_type=self.kind.pk, severity='MEDIUM', admin_note='Đã kiểm tra', version=revision(Violation.objects.get(pk=self.violation.pk)))
        payload.update(overrides)
        return self.client.post(self.url('violation-review', self.violation.pk), payload)

    def test_admin_list_search_filter_and_evidence_detail(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url('violations')), '43C-11111')
        self.assertNotContains(self.client.get(self.url('violations'), {'q': 'unknown'}), '43C-11111')
        self.assertNotContains(self.client.get(self.url('violations'), {'status': 'APPROVED'}), '43C-11111')
        Evidence.objects.create(violation=self.violation, type='VIDEO', url='https://example.com/clip.mp4', captured_at=timezone.now())
        response = self.client.get(self.url('violation-detail', self.violation.pk))
        self.assertContains(response, self.evidence.url)
        self.assertContains(response, '<video controls')
        self.assertContains(response, 'Xác nhận vi phạm')
        self.assertNotContains(response, '/static/app.js')

    def test_driver_visibility_is_enforced_on_list_and_detail(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url('violations')), '43C-11111')
        self.assertEqual(self.client.get(self.url('violation-detail', self.violation.pk)).status_code, 404)
        self.client.force_login(self.driver)
        for status in Violation.Status.values:
            self.violation.status = status
            self.violation.save()
            response = self.client.get(self.url('violation-detail', self.violation.pk))
            visible = status in ('PENDING', 'APPROVED')
            self.assertEqual(response.status_code, 200 if visible else 404)
            listing = self.client.get(self.url('violations'))
            if visible:
                self.assertContains(listing, '43C-11111')
                self.assertNotContains(response, 'name="action"')
            else:
                self.assertNotContains(listing, '43C-11111')

    def test_anonymous_driver_and_csrf_cannot_review(self):
        self.assertEqual(self.client.get(self.url('violations')).status_code, 302)
        self.assertEqual(self.review().status_code, 302)
        self.client.force_login(self.driver)
        self.assertEqual(self.review().status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('violation-review', self.violation.pk)).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url('violation-review', self.violation.pk), {'action': 'approve'}).status_code, 403)
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'PENDING')

    def test_review_preserves_detection_and_session_and_rejects_stale_submission(self):
        self.client.force_login(self.admin)
        original_time = self.violation.detected_at
        response = self.review(detected_at='2000-01-01', session='99999', status='REVOKED')
        self.assertRedirects(response, self.url('violation-detail', self.violation.pk))
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'APPROVED')
        self.assertEqual(self.violation.severity, 'MEDIUM')
        self.assertEqual(self.violation.detected_at, original_time)
        self.assertEqual(self.violation.session_id, self.session.pk)
        self.review(action='reject', admin_note='Stale form')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'APPROVED')
        self.assertEqual(self.violation.admin_note, 'Đã kiểm tra')

    def test_missing_evidence_and_invalid_review_do_not_approve(self):
        self.client.force_login(self.admin)
        self.evidence.delete()
        self.assertContains(self.review(), 'Cần có ít nhất một bằng chứng')
        self.review(severity='INVALID')
        self.review(action='invalid')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'PENDING')
        self.assertEqual(self.violation.severity, 'HIGH')
        self.assertEqual(self.violation.admin_note, '')

    def test_reject_reopen_preserves_evidence(self):
        self.client.force_login(self.admin)
        self.review(action='reject')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'REJECTED')
        self.review(action='reopen')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'PENDING')
        self.assertTrue(self.violation.evidences.filter(pk=self.evidence.pk).exists())

    def test_reopen_with_existing_appeal_is_deferred(self):
        self.violation.status = 'REVOKED'
        self.violation.save()
        Appeal.objects.create(violation=self.violation, content='Xin xem xét')
        self.client.force_login(self.admin)
        self.review(action='reopen')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'REVOKED')

    def test_type_management_normalizes_codes_and_is_admin_only(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(self.url('violation-types')).status_code, 403)
        self.assertEqual(self.client.post(self.url('create', 'violation-types'), {}).status_code, 403)
        self.client.force_login(self.admin)
        payload = dict(code=' looking back ', name='Quay đầu', description='')
        self.assertRedirects(self.client.post(self.url('create', 'violation-types'), payload), self.url('violation-types'))
        self.assertTrue(ViolationType.objects.filter(code='LOOKING_BACK').exists())
        payload['code'] = 'looking_back'
        self.assertEqual(self.client.post(self.url('create', 'violation-types'), payload).status_code, 200)
        self.assertEqual(ViolationType.objects.filter(code='LOOKING_BACK').count(), 1)

    def test_foreign_keys_cascade_and_unique_appeal(self):
        with self.assertRaises(ProtectedError):
            self.kind.delete()
        with self.assertRaises(ProtectedError):
            self.session.delete()
        Appeal.objects.create(violation=self.violation, content='Xin xem xét')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appeal.objects.create(violation=self.violation, content='Lần hai')
        self.violation.delete()
        self.assertFalse(Evidence.objects.exists())
        self.assertFalse(Appeal.objects.exists())
        self.assertTrue(DrivingSession.objects.exists())

    def test_database_rejects_invalid_status_severity_and_case_duplicate_code(self):
        for values in ({'status': 'UNKNOWN'}, {'severity': 'EXTREME'}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Violation.objects.filter(pk=self.violation.pk).update(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ViolationType.objects.bulk_create([ViolationType(code='phone_usage', name='Duplicate')])

    def test_unsafe_evidence_url_and_admin_note_are_not_rendered_as_html(self):
        self.evidence.url = 'javascript:alert(1)'
        self.evidence.save()
        self.violation.admin_note = '<script>alert(1)</script>'
        self.violation.save()
        self.client.force_login(self.driver)
        response = self.client.get(self.url('violation-detail', self.violation.pk))
        self.assertNotContains(response, 'javascript:')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_empty_list_pagination_and_no_web_creation(self):
        self.client.force_login(self.admin)
        for index in range(21):
            Violation.objects.create(session=self.session, violation_type=self.kind, severity='LOW', detected_at=timezone.now())
        response = self.client.get(self.url('violations'), {'page': '2'})
        self.assertEqual(response.context['pagination'].number, 2)
        self.assertEqual(len(response.context['rows']), 2)
        self.assertEqual(self.client.post(self.url('create', 'violations'), {}).status_code, 403)
        Violation.objects.all().delete()
        self.assertContains(self.client.get(self.url('violations')), 'Chưa có dữ liệu phù hợp.')

    def test_invalid_evidence_blocks_approval_and_creates_no_history(self):
        self.evidence.url = 'javascript:alert(1)'
        self.evidence.save()
        self.client.force_login(self.admin)
        self.assertContains(self.review(), 'đường dẫn không hợp lệ')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'PENDING')
        self.assertFalse(ViolationReview.objects.exists())

    def test_audit_preserves_actor_and_previous_decision_after_reopen(self):
        self.client.force_login(self.admin)
        old_version = revision(self.violation)
        self.review()
        self.review(action='reopen')
        self.review(action='reject', version=old_version)
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'PENDING')
        history = list(self.violation.reviews.order_by('pk'))
        self.assertEqual([item.action for item in history], ['approve', 'reopen'])
        self.assertEqual(history[0].reviewer_id, self.admin.pk)
        self.assertEqual(history[0].before['severity'], 'HIGH')
        self.assertEqual(history[0].after['severity'], 'MEDIUM')
        self.assertEqual(history[0].after['status'], 'APPROVED')
        self.kind.name = 'Renamed'
        self.kind.save()
        history[0].refresh_from_db()
        self.assertNotEqual(history[0].after['type_name'], self.kind.name)
        self.assertContains(self.client.get(self.url('violation-detail', self.violation.pk)), 'Lịch sử xử lý')
        self.client.force_login(self.driver)
        self.assertNotContains(self.client.get(self.url('violation-detail', self.violation.pk)), 'Lịch sử xử lý')

    def test_archived_appeal_still_prevents_second_appeal(self):
        appeal = Appeal.objects.create(violation=self.violation, content='Original content')
        appeal.delete()
        self.assertIsNotNone(appeal.deleted_at)
        self.assertEqual(Appeal.objects.get(pk=appeal.pk).content, 'Original content')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appeal.objects.create(violation=self.violation, content='Second attempt')
        self.assertEqual(Appeal.objects.filter(pk=appeal.pk).delete()[0], 0)
        self.violation.delete()
        self.assertFalse(Appeal.objects.exists())
