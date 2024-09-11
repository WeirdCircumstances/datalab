from django.db import models

from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet



@register_snippet
class Navigator(models.Model):
    name = models.CharField(max_length=255, help_text='Der Name, der im Menu gezeigt werden soll.')
    html_id = models.CharField(max_length=255, help_text='ein eindeutiger Bezeichner, keine Dopplungen, keine Leerzeichen')

    panels = [
        FieldPanel("name"),
        FieldPanel("html_id"),
    ]

    def __str__(self):
        return self.name
