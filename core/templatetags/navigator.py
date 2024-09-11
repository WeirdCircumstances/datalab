from django import template
from ..models import Navigator

register = template.Library()

@register.simple_tag()
def navigation():
    return {
        'navigator': Navigator.objects.all(),
    }
