import string
import random

from django import template

# import site:
from wagtail.models import Site

# from base.models import FooterText

from blog.models import BlogHome, TravelBlogHome
from home.models import GalleryPage

register = template.Library()


# ... keep the definition of get_footer_text and add the get_site_root template tag:
@register.simple_tag(takes_context=True)
def get_blog_root(context):
    return BlogHome.objects.all().first()  # Site.find_for_request(context["request"]).root_page


@register.simple_tag(takes_context=True)
def get_gallery(context):
    return GalleryPage.objects.all()


@register.simple_tag(takes_context=True)
def get_travel_blog_root(context):
    return TravelBlogHome.objects.all().first()  # Site.find_for_request(context["request"]).root_page

@register.simple_tag(takes_context=True)
def random_string(context):
    random_digits = string.digits
    return ''.join(random.choice(random_digits) for _ in range(5))