from django.db import models
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import StreamField

from wagtail.models import Page
from home import blocks as block


class HomePage(Page):
    parent_page_types = ['wagtailcore.Page']

    header = StreamField([
        ('heros', block.HeroBlock()),
    ], null=True, min_num=1, max_num=1)


    body = StreamField([
        ('blog_entry', block.BlogBlock()),
        ('paragraph', block.ParagraphBlock()),
        #('buttons', block.ButtonBlock()),
        #('contact', block.ContactBlock()),
        ('big_image', block.BigImageBlock()),
        ('bricks', block.BrickBlock()),
    ], default=None)

    content_panels = Page.content_panels + [
        FieldPanel('header'),
        # FieldPanel('blog'),
        FieldPanel('body'),
    ]

class ImpressumPage(Page):
    parent_page_types = ['home.HomePage']
    #
    # header = StreamField([
    #     ('heros', block.HeroBlock()),
    # ], null=True, min_num=1, max_num=1)

    body = StreamField([
        # ('blog_entry', block.BlogBlock()),
        ('paragraph', block.ParagraphBlock()),
        # ('buttons', block.ButtonBlock()),
        # ('contact', block.ContactBlock()),
        # ('big_image', block.BigImageBlock()),
        # ('bricks', block.BrickBlock()),
    ], default=None)

    content_panels = Page.content_panels + [
        #FieldPanel('header'),
        # FieldPanel('blog'),
        FieldPanel('body'),
    ]


class GalleryPage(Page):
    parent_page_types = ['home.HomePage']
    #
    # header = StreamField([
    #     ('heros', block.HeroBlock()),
    # ], null=True, min_num=1, max_num=1)

    body = StreamField([
        #('blog_entry', block.BlogBlock()),
        #('paragraph', block.ParagraphBlock()),
        #('buttons', block.ButtonBlock()),
        #('contact', block.ContactBlock()),
        #('big_image', block.BigImageBlock()),
        ('bricks', block.BrickBlock()),
        ('iNaturalist', block.INaturalistWidgetBlock())
    ], default=None)

    content_panels = Page.content_panels + [
        #FieldPanel('header'),
        # FieldPanel('blog'),
        FieldPanel('body'),
    ]
