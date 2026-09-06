from django.urls import reverse
from django.views.generic import TemplateView


class FrontendView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        from .urls import PAGE_NAMES

        context = super().get_context_data(**kwargs)
        context['frontend_routes'] = {
            name: reverse(f'frontend:{name}') for name in PAGE_NAMES
        }
        context['frontend_routes']['home'] = reverse('frontend:home')
        return context
