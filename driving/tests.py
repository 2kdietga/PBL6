from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, DriverProfile
from vehicles.models import Vehicle, VehicleType, DriverVehicleAssignment
from .models import DrivingSession


class SessionConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user('driver')
        driver = DriverProfile.objects.create(user=user, full_name='Driver', date_of_birth=date(1990,1,1), phone='123', address='City')
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        cls.vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='43C-12345', load_capacity=5000)
        cls.assignment = DriverVehicleAssignment.objects.create(driver=driver, vehicle=cls.vehicle, start_at=timezone.now())
        cls.other_assignment = DriverVehicleAssignment.objects.create(driver=driver, vehicle=cls.vehicle, start_at=timezone.now())

    def test_vehicle_derived_and_unique_across_assignments(self):
        first = DrivingSession.objects.create(assignment=self.assignment, started_at=timezone.now())
        self.assertEqual(first.vehicle_id, self.vehicle.pk)
        with self.assertRaises(ValidationError):
            DrivingSession.objects.create(assignment=self.other_assignment, started_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            DrivingSession.objects.bulk_create([DrivingSession(assignment=self.other_assignment, vehicle=self.vehicle, started_at=timezone.now())])
        first.status, first.ended_at = 'ENDED', timezone.now()
        first.save()
        DrivingSession.objects.create(assignment=self.other_assignment, started_at=timezone.now())

    def test_database_blocks_inconsistent_status_and_times(self):
        first = DrivingSession.objects.create(assignment=self.assignment, started_at=timezone.now())
        for values in ({'status':'ENDED'}, {'ended_at':timezone.now()},
                       {'status':'ENDED','ended_at':first.started_at-timedelta(seconds=1)}, {'status':'INVALID'}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                DrivingSession.objects.filter(pk=first.pk).update(**values)

    def test_cannot_reassign_or_reopen_ended_session(self):
        first = DrivingSession.objects.create(assignment=self.assignment, started_at=timezone.now())
        first.assignment = self.other_assignment
        with self.assertRaises(ValidationError): first.save()
        first.refresh_from_db()
        first.status, first.ended_at = 'ENDED', timezone.now()
        first.save()
        first.status, first.ended_at = 'STARTED', None
        with self.assertRaises(ValidationError): first.save()
        self.assignment.start_at += timedelta(days=1)
        with self.assertRaises(ValidationError): self.assignment.save()
