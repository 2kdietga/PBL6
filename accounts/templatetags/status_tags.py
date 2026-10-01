from django import template
from django.utils.html import format_html

register = template.Library()

STATUS_TONES = {
    'APPROVED': 'good', 'ACTIVE': 'good', 'ONLINE': 'good',
    'PENDING': 'warn', 'INCOMPLETE': 'warn', 'MAINTENANCE': 'warn',
    'REJECTED': 'bad', 'EXPIRED': 'bad', 'OFFLINE': 'bad', 'DISABLED': 'bad',
    'STARTED': 'info', 'ENDED': 'neutral', 'INACTIVE': 'neutral', 'REVOKED': 'neutral',
}


@register.simple_tag
def status_badge(code, label):
    """Keep the readable label and escape it while adding a semantic color."""
    return format_html('<span class="tag {}">{}</span>', STATUS_TONES.get(code, 'neutral'), label)
