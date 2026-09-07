from io import BytesIO
from datetime import date
from unittest.mock import patch, Mock

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from accounts.media_services import MediaError, extract_embedding
from .forms import ProfileForm


def image_file(name='face.png'):
    stream = BytesIO()
    Image.new('RGB', (32, 32), 'white').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')


class UploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('driver', password='Secret123!')
        self.driver = DriverProfile.objects.create(user=self.user, full_name='Minh', date_of_birth=date(1990,1,1), phone='0905111111', address='Đà Nẵng')
        self.client.force_login(self.user)
        self.profile = dict(full_name='Minh', date_of_birth='1990-01-01', phone='0905111111', address='Đà Nẵng')
        self.license = dict(license_number='123456', license_class='C', issued_date='2025-01-01', expiry_date='2030-01-01')

    @patch('accounts.profile_services.upload_image', return_value=('https://res.cloudinary.com/test/face.png', 'face-new'))
    @patch('accounts.profile_services.extract_embedding', return_value=[0.2, 0.4, 0.6])
    def test_avatar_and_vector_persist_and_replacement_needs_review(self, extract, upload):
        payload = {**self.profile, 'avatar': image_file(), 'extra_images':[image_file('side.png')]}
        self.assertRedirects(self.client.post(reverse('frontend:profile'), payload), reverse('frontend:profile'))
        face = FaceProfile.objects.get(driver=self.driver)
        self.assertEqual(face.embedding, [0.2,0.4,0.6])
        self.assertEqual(len(extract.call_args.args[0]), 2)
        self.assertEqual(face.cloudinary_public_id, 'face-new')
        face.approval_status = 'APPROVED'
        face.save()
        with patch('accounts.profile_services.delete_images') as cleanup, self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('frontend:profile'), {**self.profile, 'avatar':image_file()})
        face.refresh_from_db()
        self.assertEqual(face.approval_status, 'PENDING')
        self.assertEqual(FaceProfile.objects.count(), 1)
        cleanup.assert_called_once_with(['face-new'])

    @patch('accounts.profile_services.upload_image')
    @patch('accounts.profile_services.extract_embedding', side_effect=MediaError('Nhận diện thất bại'))
    def test_embedding_failure_preserves_profile(self, extract, upload):
        response = self.client.post(reverse('frontend:profile'), {**self.profile, 'full_name':'Tên mới', 'avatar':image_file()})
        self.assertContains(response, 'Nhận diện thất bại')
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.full_name, 'Minh')
        self.assertFalse(FaceProfile.objects.exists())
        upload.assert_not_called()

    @patch('accounts.profile_services.upload_image', side_effect=[('https://res.cloudinary.com/test/front.png','front-new'), ('https://res.cloudinary.com/test/back.png','back-new')])
    def test_license_requires_files_and_saves_public_ids(self, upload):
        self.client.post(reverse('frontend:license'), self.license)
        self.assertFalse(DriverLicense.objects.exists())
        payload = {**self.license, 'front_image':image_file('front.png'), 'back_image':image_file('back.png')}
        self.assertRedirects(self.client.post(reverse('frontend:license'), payload), reverse('frontend:license'))
        obj = DriverLicense.objects.get(driver=self.driver)
        self.assertEqual(obj.front_image_public_id, 'front-new')
        self.assertEqual(obj.back_image_public_id, 'back-new')
        self.client.post(reverse('frontend:license'), self.license)
        obj.refresh_from_db()
        self.assertEqual(obj.front_image_public_id, 'front-new')
        self.assertEqual(upload.call_count, 2)

    @patch('accounts.profile_services.delete_images')
    @patch('accounts.profile_services.upload_image', side_effect=[('https://res.cloudinary.com/test/front.png','orphan'), MediaError('Upload thất bại')])
    def test_second_upload_failure_cleans_first_and_does_not_save(self, upload, cleanup):
        response = self.client.post(reverse('frontend:license'), {**self.license, 'front_image':image_file(), 'back_image':image_file()})
        self.assertContains(response, 'Upload thất bại')
        self.assertFalse(DriverLicense.objects.exists())
        cleanup.assert_called_once_with(['orphan'])

    @patch('accounts.profile_services.extract_embedding')
    def test_fake_image_is_rejected_before_remote_call(self, extract):
        response = self.client.post(reverse('frontend:profile'), {**self.profile, 'avatar':SimpleUploadedFile('bad.png', b'not-an-image', content_type='image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        extract.assert_not_called()

    def test_extra_images_count_is_limited(self):
        from django.utils.datastructures import MultiValueDict
        form = ProfileForm(self.profile, MultiValueDict({'avatar':[image_file()], 'extra_images':[image_file() for _ in range(5)]}), instance=self.driver)
        self.assertFalse(form.is_valid())
        self.assertIn('extra_images', form.errors)

    @patch('accounts.profile_services.delete_images')
    @patch('accounts.profile_services.upload_image', return_value=('https://res.cloudinary.com/test/face.png', 'new'))
    @patch('accounts.profile_services.extract_embedding', return_value=[0.2,0.4])
    @patch('accounts.profile_services.FaceProfile.save', side_effect=RuntimeError('database failure'))
    def test_database_failure_rolls_back_profile_and_cleans_uploaded_avatar(self, save, extract, upload, cleanup):
        with self.assertRaises(RuntimeError):
            self.client.post(reverse('frontend:profile'), {**self.profile, 'full_name':'Tên mới', 'avatar':image_file()})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.full_name, 'Minh')
        cleanup.assert_called_with(['new'])


class EmbeddingContractTests(SimpleTestCase):
    @override_settings(FACE_EMBEDDING_URL='https://example.com/extract_profile')
    @patch('accounts.media_services.requests.post')
    def test_notebook_multipart_contract(self, post):
        post.return_value = Mock(status_code=200, json=lambda: {'vector':[0.2,0.3]})
        self.assertEqual(extract_embedding([image_file(), image_file()]), [0.2,0.3])
        self.assertEqual([item[0] for item in post.call_args.kwargs['files']], ['files','files'])
        self.assertEqual(post.call_args.args[0], 'https://example.com/extract_profile')
        self.assertIn('timeout', post.call_args.kwargs)

    @patch('accounts.media_services.requests.post')
    def test_invalid_vectors_rejected(self, post):
        for vector in ([], [float('nan')], [[1,2]], [True], [0,0], 'bad'):
            post.return_value = Mock(status_code=200, json=lambda: {'vector':vector})
            with self.assertRaises(MediaError): extract_embedding([image_file()])

    @patch('accounts.media_services.requests.post')
    def test_unavailable_service_is_not_reported_as_bad_image(self, post):
        post.return_value = Mock(status_code=503)
        with self.assertRaisesMessage(MediaError, 'tạm ngừng (HTTP 503)'):
            extract_embedding([image_file()])

    @patch('accounts.media_services.requests.post')
    def test_invalid_endpoint_has_configuration_message(self, post):
        post.return_value = Mock(status_code=404)
        with self.assertRaisesMessage(MediaError, 'FACE_EMBEDDING_URL'):
            extract_embedding([image_file()])

    @patch('accounts.media_services.requests.post')
    def test_rejected_image_has_image_message(self, post):
        post.return_value = Mock(status_code=422)
        with self.assertRaisesMessage(MediaError, 'không nhận diện được ảnh'):
            extract_embedding([image_file()])
