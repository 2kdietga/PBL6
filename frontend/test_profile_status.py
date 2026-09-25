from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from accounts.concurrency import revision
from vehicles.models import Vehicle, VehicleType, DriverVehicleAssignment
from .forms import AssignmentForm


class ProfileStatusTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', role='ADMIN')
        self.driver = DriverProfile.objects.create(
            user=User.objects.create_user('driver'), full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='0905000000', address='Da Nang')
        self.client.force_login(self.admin)
        self.url = reverse('frontend:driver-action', args=[self.driver.pk])
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        self.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='TEST', load_capacity=1000)

    def approve(self):
        self.driver.refresh_from_db()
        self.client.post(self.url, {'action': 'approve', 'version': revision(self.driver)})
        self.driver.refresh_from_db()

    def complete(self):
        self.license = DriverLicense.objects.create(
            driver=self.driver, license_number='123', license_class='C',
            issued_date=date(2020, 1, 1), expiry_date=timezone.localdate()+timedelta(days=365),
            front_image_url='https://example.com/front', back_image_url='https://example.com/back')
        self.face = FaceProfile.objects.create(driver=self.driver, face_image_url='https://example.com/face', embedding=[1, 2])

    def assignment_form(self, **kwargs):
        return AssignmentForm(dict(driver=self.driver.pk, vehicle=self.vehicle.pk, start_at=timezone.now()), **kwargs)

    def test_missing_evidence_cannot_be_approved_or_assigned(self):
        self.approve()
        self.assertEqual(self.driver.approval_status, 'INCOMPLETE')
        self.assertFalse(self.assignment_form().is_valid())
        self.complete()
        self.face.face_image_url = ''
        self.face.save()
        self.approve()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.assertFalse(self.driver.can_approve)

    def test_pending_face_takes_priority_over_missing_license(self):
        face = FaceProfile.objects.create(driver=self.driver,
            face_image_url='https://example.com/face', embedding=[1, 2])
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.approve()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.assertFalse(self.assignment_form().is_valid())
        self.client.post(self.url, {'action': 'face-approve', 'version': revision(face)})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'INCOMPLETE')

    def test_pending_license_takes_priority_over_missing_face(self):
        self.complete()
        self.face.delete()
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.client.post(self.url, {'action': 'license-approve', 'version': revision(self.license)})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'INCOMPLETE')

    def test_complete_evidence_requires_reviews_then_overall_approval(self):
        self.complete()
        self.approve()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        for obj, action in ((self.license, 'license-approve'), (self.face, 'face-approve')):
            self.client.post(self.url, {'action': action, 'version': revision(obj)})
        self.approve()
        self.assertEqual(self.driver.approval_status, 'APPROVED')
        self.assertTrue(self.assignment_form().is_valid())
        self.license.refresh_from_db()
        self.license.status = 'PENDING'
        self.license.save()
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'PENDING')
        self.assertFalse(self.assignment_form().is_valid())

    def test_missing_or_expired_evidence_blocks_previously_approved_profile(self):
        self.complete()
        self.face.approval_status = 'APPROVED'
        self.face.save()
        self.license.status = 'ACTIVE'
        self.license.save()
        self.approve()
        assignment = DriverVehicleAssignment.objects.create(
            driver=self.driver, vehicle=self.vehicle, start_at=timezone.now()-timedelta(days=1))
        # Date changes must be checked even without saving the license again.
        DriverLicense.objects.filter(pk=self.license.pk).update(expiry_date=timezone.localdate())
        self.assertFalse(self.assignment_form().is_valid())
        form = AssignmentForm(dict(driver=self.driver.pk, vehicle=self.vehicle.pk,
                                   start_at=assignment.start_at, end_at=timezone.now()), instance=assignment)
        self.assertTrue(form.is_valid(), form.errors)
        self.face.delete()
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'INCOMPLETE')
