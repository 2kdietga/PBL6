from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse


class FrontendTests(SimpleTestCase):
    def test_frontend_renders_without_database(self):
        response = self.client.get(reverse('frontend:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="vi"')
        self.assertContains(response, '/static/server.js')
        self.assertContains(response, '/static/app.css')
        self.assertNotContains(response, '/static/app.js')

    def test_named_pages_can_be_opened_directly(self):
        for page in ('dashboard', 'drivers', 'vehicles', 'assignments', 'sessions', 'devices', 'catalogs', 'profile', 'license'):
            with self.subTest(page=page):
                url = reverse(f'frontend:{page}')
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('frontend:login')))

    def test_unknown_page_is_not_a_frontend_route(self):
        self.assertEqual(self.client.get('/unknown-page/').status_code, 404)

    def test_assets_are_discoverable(self):
        for asset in ('server.js', 'app.css', 'css/server.css'):
            self.assertIsNotNone(finders.find(asset))
