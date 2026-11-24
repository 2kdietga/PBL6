from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.concurrency import revision
from accounts.models import User, DriverProfile, FaceProfile, FaceProcessingJob
from accounts.face_jobs import claim_job, enqueue_face, process_next_face_job
from accounts.media_services import MediaError
from django.db import transaction


def image():
    buffer = BytesIO()
    Image.new('RGB', (24, 24)).save(buffer, format='PNG')
    return SimpleUploadedFile('face.png', buffer.getvalue(), content_type='image/png')


class FaceJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('driver')
        self.other = User.objects.create_user('other')
        self.driver = DriverProfile.objects.create(user=self.user, full_name='Driver',
            date_of_birth=date(1990, 1, 1), phone='123', address='City')
        self.face = FaceProfile.objects.create(driver=self.driver, face_image_url='https://example.com/old.png',
            cloudinary_public_id='old', embedding=[1.0]+[0.0]*511, approval_status='APPROVED')
        self.driver.refresh_from_db()
        self.client.force_login(self.user)

    def queue(self):
        with transaction.atomic():
            return enqueue_face(self.driver, image(), [], False)

    def test_save_returns_without_network_and_text_edits_do_not_cancel_job(self):
        payload = dict(full_name='Updated', date_of_birth='1990-01-01', phone='123', address='City',
                       version=revision(self.driver), avatar=image())
        with patch('accounts.face_jobs.extract_embedding') as extract, patch('accounts.face_jobs.upload_image') as upload:
            self.assertEqual(self.client.post(reverse('frontend:profile'), payload).status_code, 302)
            extract.assert_not_called()
            upload.assert_not_called()
        job = FaceProcessingJob.objects.get(driver=self.driver)
        token = job.token
        self.assertEqual(job.images.count(), 1)
        self.face.refresh_from_db()
        self.assertEqual(self.face.approval_status, 'APPROVED')
        self.driver.refresh_from_db()
        payload.pop('avatar')
        payload['version'] = revision(self.driver)
        payload['phone'] = '456'
        self.client.post(reverse('frontend:profile'), payload)
        job.refresh_from_db()
        self.assertEqual(job.token, token)
        self.assertEqual(job.images.count(), 1)

    def test_claim_is_exclusive_and_expired_lease_is_recovered(self):
        job = self.queue()
        claimed, images = claim_job()
        self.assertIsNone(claim_job())
        self.assertEqual(len(images), 1)
        FaceProcessingJob.objects.filter(pk=job.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        recovered, _ = claim_job()
        self.assertNotEqual(recovered.token, claimed.token)
        self.assertEqual(recovered.attempts, 2)

    @patch('accounts.face_jobs.delete_images')
    @patch('accounts.face_jobs.upload_image', return_value=('https://example.com/new.png', 'new'))
    @patch('accounts.face_jobs.extract_embedding', return_value=[0.0, 1.0]+[0.0]*510)
    def test_success_replaces_face_and_deletes_temporary_images(self, extract, upload, cleanup):
        job = self.queue()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(process_next_face_job())
        job.refresh_from_db()
        self.face.refresh_from_db()
        self.assertEqual(job.status, 'DONE')
        self.assertFalse(job.images.exists())
        self.assertEqual(job.uploaded_ids, [])
        self.assertEqual(self.face.approval_status, 'PENDING')
        self.assertEqual(self.face.embedding, [0.0, 1.0]+[0.0]*510)
        cleanup.assert_any_call(['old'])
        self.assertFalse(process_next_face_job())

    @patch('accounts.face_jobs.extract_embedding', side_effect=MediaError('AI unavailable'))
    def test_failure_retries_then_allows_manual_retry_without_losing_old_face(self, extract):
        job = self.queue()
        for _ in range(3):
            FaceProcessingJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
            process_next_face_job()
        job.refresh_from_db()
        self.face.refresh_from_db()
        self.assertEqual(job.status, 'FAILED')
        self.assertEqual(job.attempts, 3)
        self.assertEqual(self.face.cloudinary_public_id, 'old')
        self.assertEqual(self.face.approval_status, 'APPROVED')
        self.assertEqual(job.images.count(), 1)
        self.assertFalse(process_next_face_job())
        url = reverse('frontend:face-job-retry', args=[job.pk])
        self.client.post(url, {'token': 'stale'})
        job.refresh_from_db()
        self.assertEqual(job.status, 'FAILED')
        self.client.post(url, {'token': str(job.token)})
        job.refresh_from_db()
        self.assertEqual(job.status, 'QUEUED')
        self.assertEqual(job.attempts, 0)

    @patch('accounts.face_jobs.delete_images')
    @patch('accounts.face_jobs.upload_image', return_value=('https://example.com/stale.png', 'stale-upload'))
    def test_reupload_during_processing_cannot_publish_old_result(self, upload, cleanup):
        job = self.queue()
        def replace_while_uploading(*args):
            self.queue()
            return ('https://example.com/stale.png', 'stale-upload')
        upload.side_effect = replace_while_uploading
        with patch('accounts.face_jobs.extract_embedding', return_value=[1.0]+[0.0]*511):
            process_next_face_job()
        self.face.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(self.face.cloudinary_public_id, 'old')
        self.assertEqual(job.status, 'QUEUED')
        self.assertEqual(job.images.count(), 1)
        cleanup.assert_any_call(['stale-upload'])

    def test_status_and_retry_are_private_and_csrf_protected(self):
        job = self.queue()
        url = reverse('frontend:face-job-status', args=[job.pk])
        response = self.client.get(url)
        self.assertEqual(response.json()['status'], 'QUEUED')
        self.assertNotIn('data', response.json())
        self.assertNotIn('embedding', response.json())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(reverse('frontend:face-job-retry', args=[job.pk])).status_code, 404)
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse('frontend:face-job-retry', args=[job.pk])).status_code, 403)
