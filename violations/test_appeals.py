from datetime import date

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.concurrency import revision
from accounts.models import User, DriverProfile
from driving.models import DrivingSession
from vehicles.models import VehicleType, Vehicle, DriverVehicleAssignment
from .models import Appeal, Violation, ViolationType, ViolationReview


class AppealTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.driver = User.objects.create_user('driver')
        cls.other = User.objects.create_user('other')
        cls.admin = User.objects.create_user('admin', role='ADMIN')
        profile = DriverProfile.objects.create(user=cls.driver, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='TEST', load_capacity=1000)
        assignment = DriverVehicleAssignment.objects.create(driver=profile, vehicle=vehicle, start_at=timezone.now())
        session = DrivingSession.objects.create(assignment=assignment, started_at=timezone.now())
        violation_type = ViolationType.objects.create(code='PHONE', name='Phone')
        cls.violation = Violation.objects.create(session=session, violation_type=violation_type,
            severity='MEDIUM', detected_at=timezone.now(), status='APPROVED')

    def url(self, name):
        return reverse('frontend:' + name, args=[self.violation.pk])

    def submit(self, **overrides):
        data = dict(content='Please review the evidence', version=revision(Violation.objects.get(pk=self.violation.pk)))
        data.update(overrides)
        return self.client.post(self.url('appeal-submit'), data)

    def resolve(self, **overrides):
        data = dict(action='appeal_approve', admin_response='Evidence does not support violation',
                    version=revision(Violation.objects.get(pk=self.violation.pk)))
        data.update(overrides)
        return self.client.post(self.url('appeal-review'), data)

    def test_driver_submits_once_and_sees_pending_appeal(self):
        self.client.force_login(self.driver)
        self.assertContains(self.client.get(self.url('violation-detail')), 'Gửi kháng cáo')
        self.assertRedirects(self.submit(status='APPROVED'), self.url('violation-detail'))
        appeal = Appeal.objects.get()
        self.assertEqual(appeal.status, 'PENDING')
        self.submit(content='Duplicate')
        self.assertEqual(Appeal.objects.count(), 1)
        self.assertContains(self.client.get(reverse('frontend:appeals')), f'KC-{appeal.pk}')
        self.assertNotContains(self.client.get(self.url('violation-detail')), '>Gửi kháng cáo</button>')

    def test_only_approved_violation_can_be_appealed(self):
        self.client.force_login(self.driver)
        for state in ('PENDING', 'REJECTED', 'REVOKED'):
            Violation.objects.filter(pk=self.violation.pk).update(status=state)
            self.submit()
            self.assertFalse(Appeal.objects.exists())

    def test_whitespace_oversized_and_stale_content_rejected(self):
        self.client.force_login(self.driver)
        for content in ('   ', 'x' * 5001):
            response = self.submit(content=content)
            self.assertEqual(response.status_code, 200)
            self.assertIn('content', response.context['appeal_form'].errors)
        self.submit(version='stale')
        self.assertFalse(Appeal.objects.exists())

    def test_ownership_permissions_methods_and_csrf(self):
        self.assertEqual(self.submit().status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.submit().status_code, 404)
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(self.url('appeal-submit')).status_code, 405)
        self.assertEqual(self.resolve().status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.driver)
        self.assertEqual(csrf_client.post(self.url('appeal-submit'), {'content': 'Test'}).status_code, 403)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url('appeal-review'), {}).status_code, 403)
        self.assertFalse(Appeal.objects.exists())

    def test_acceptance_revokes_violation_and_keeps_driver_access_and_audit(self):
        self.client.force_login(self.driver)
        self.submit()
        self.client.force_login(self.admin)
        old_version = revision(Violation.objects.get(pk=self.violation.pk))
        self.assertRedirects(self.resolve(), self.url('violation-detail'))
        appeal = Appeal.objects.get()
        self.violation.refresh_from_db()
        self.assertEqual(appeal.status, 'APPROVED')
        self.assertIsNotNone(appeal.resolved_at)
        self.assertEqual(self.violation.status, 'REVOKED')
        audit = ViolationReview.objects.get()
        self.assertEqual(audit.reviewer_id, self.admin.pk)
        self.assertEqual(audit.action, 'appeal_approve')
        self.assertEqual(audit.before['status'], 'APPROVED')
        self.assertEqual(audit.after['status'], 'REVOKED')
        self.resolve(action='appeal_reject', version=old_version)
        self.assertEqual(ViolationReview.objects.count(), 1)
        self.client.force_login(self.driver)
        self.assertContains(self.client.get(self.url('violation-detail')), appeal.admin_response)
        self.assertContains(self.client.get(reverse('frontend:appeals')), f'KC-{appeal.pk}')
        self.assertContains(self.client.get(reverse('frontend:violations')), 'TEST')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url('violation-detail')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('frontend:appeals')), f'KC-{appeal.pk}')

    def test_rejection_keeps_violation_and_requires_response(self):
        self.client.force_login(self.driver)
        self.submit()
        self.client.force_login(self.admin)
        response = self.resolve(admin_response=' ')
        self.assertIn('admin_response', response.context['appeal_review_form'].errors)
        self.assertEqual(Appeal.objects.get().status, 'PENDING')
        self.resolve(action='unknown')
        self.assertFalse(ViolationReview.objects.exists())
        self.resolve(action='appeal_reject', admin_response='Evidence confirms violation')
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, 'APPROVED')
        self.assertEqual(Appeal.objects.get().status, 'REJECTED')
        self.client.force_login(self.driver)
        self.submit()
        self.assertEqual(Appeal.objects.count(), 1)

    def test_archived_appeal_cannot_be_resubmitted_or_resolved(self):
        appeal = Appeal.objects.create(violation=self.violation, content='Original')
        appeal.delete()
        self.client.force_login(self.driver)
        self.submit()
        self.assertEqual(Appeal.objects.count(), 1)
        self.client.force_login(self.admin)
        self.resolve()
        self.assertFalse(ViolationReview.objects.exists())

    def test_content_and_response_are_escaped(self):
        self.client.force_login(self.driver)
        self.submit(content='<script>alert(1)</script>')
        self.client.force_login(self.admin)
        self.resolve(admin_response='<script>alert(2)</script>')
        self.client.force_login(self.driver)
        response = self.client.get(self.url('violation-detail'))
        self.assertNotContains(response, '<script>alert')
        self.assertContains(response, '&lt;script&gt;alert(1)')
        self.assertContains(response, '&lt;script&gt;alert(2)')
