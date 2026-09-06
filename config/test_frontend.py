from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse
from frontend.urls import PAGE_NAMES


class FrontendTests(SimpleTestCase):
    def test_frontend_renders_without_database(self):
        response = self.client.get(reverse('frontend:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="vi"')
        self.assertContains(response, '/static/app.js')
        self.assertContains(response, '/static/app.css')
        self.assertContains(response, 'type="module"')

    def test_named_pages_can_be_opened_directly(self):
        for page in PAGE_NAMES:
            with self.subTest(page=page):
                url = reverse(f'frontend:{page}')
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['frontend_routes'][page], url)

    def test_unknown_page_is_not_a_frontend_route(self):
        self.assertEqual(self.client.get('/unknown-page/').status_code, 404)

    def test_assets_are_discoverable(self):
        for asset in ('app.js', 'app.css'):
            self.assertIsNotNone(finders.find(asset))
