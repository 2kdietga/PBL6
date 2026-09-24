from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import User, DriverProfile, FaceProfile
from datetime import date


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('driver', password='OriginalPassword123!')
        self.other = User.objects.create_user('other', password='OtherPassword123!')
        self.url = reverse('frontend:password-change')
        self.payload = dict(old_password='OriginalPassword123!', new_password1='DifferentSecure456!', new_password2='DifferentSecure456!')

    def test_requires_login_and_csrf(self):
        self.assertRedirects(self.client.get(self.url), reverse('frontend:login')+'?next='+self.url)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, self.payload).status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OriginalPassword123!'))

    def test_driver_without_profile_can_open_from_menu(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('frontend:dashboard')), self.url)
        response = self.client.get(self.url)
        self.assertContains(response, 'Mật khẩu hiện tại')
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertContains(response, 'type="password"')

    def test_current_face_image_is_used_as_account_avatar(self):
        profile = DriverProfile.objects.create(
            user=self.user,
            full_name='Driver',
            date_of_birth=date(1990, 1, 1),
            phone='0905000000',
            address='Đà Nẵng',
        )
        FaceProfile.objects.create(
            driver=profile,
            face_image_url='https://res.cloudinary.com/demo/image/upload/avatar.jpg',
            embedding=[0.1, 0.2],
        )
        self.client.force_login(self.user)
        for name in ('dashboard', 'password-change'):
            with self.subTest(name=name):
                response = self.client.get(reverse('frontend:' + name))
                self.assertContains(response, 'class="account-avatar"')
                self.assertContains(response, 'https://res.cloudinary.com/demo/image/upload/avatar.jpg')

    def test_account_avatar_falls_back_to_username_initial(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(response, '<span class="account-avatar" aria-hidden="true">D</span>', html=True)

    def test_admin_can_open_from_menu_and_account_summary(self):
        admin = User.objects.create_user('manager', password='AdminPassword123!', role='ADMIN')
        self.client.force_login(admin)
        response = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(response, self.url, count=2)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_wrong_current_mismatched_and_weak_password_do_not_save(self):
        self.client.force_login(self.user)
        for changes in ({'old_password': 'wrong'}, {'new_password2': 'Mismatch'},
                        {'new_password1':'123', 'new_password2':'123'}):
            response = self.client.post(self.url, {**self.payload, **changes})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('OriginalPassword123!'))
            self.assertNotContains(response, 'value="OriginalPassword123!"')
            self.assertNotContains(response, 'value="DifferentSecure456!"')

    def test_change_keeps_current_session_invalidates_others_and_only_changes_self(self):
        self.client.force_login(self.user)
        another_session = Client()
        another_session.force_login(self.user)
        response = self.client.post(self.url, {**self.payload, 'user':self.other.pk, 'role':'ADMIN'}, follow=True)
        self.assertContains(response, 'Đã đổi mật khẩu thành công')
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertTrue(self.user.check_password('DifferentSecure456!'))
        self.assertFalse(self.user.check_password('OriginalPassword123!'))
        self.assertEqual(self.user.role, 'USER')
        self.assertTrue(self.other.check_password('OtherPassword123!'))
        self.assertEqual(self.client.get(reverse('frontend:dashboard')).status_code, 200)
        self.assertEqual(another_session.get(reverse('frontend:dashboard')).status_code, 302)
        self.assertFalse(Client().login(username='driver', password='OriginalPassword123!'))
        self.assertTrue(Client().login(username='driver', password='DifferentSecure456!'))
