import random

from django import forms
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.utils.translation import get_language
# from django.contrib.sites.shortcuts import get_current_site

from modelcluster.fields import ParentalManyToManyField
# from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page, Orderable, TranslatableMixin
from wagtail.images.blocks import ImageChooserBlock
from wagtail.search import index
from wagtail.snippets.models import register_snippet
# from wagtail.models import TranslatableMixin

from home import blocks as home_blocks
from blog import blocks as blog_blocks


class BlogHome(Page):
    parent_page_types = ['home.HomePage']  # 'home.HomePage'
    template = 'blog/blog_home.html'

    # categories = ParentalManyToManyField('BlogCategory', blank=True, help_text='Welche Tags sollen in der Auswahl angezeigt werden?')

    body = StreamField([
        ('blog_cards', blog_blocks.BlogCardsBlock()),
    ], use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel('body')
    ]

    def get_context(self, request, *args, **kwargs):
        # Update context to include only published posts, ordered by reverse-chron
        context = super().get_context(request, *args, **kwargs)

        all_posts = BlogPage.objects.live().public().order_by('-first_published_at')

        # random_sample = random.sample(list(all_posts), len(all_posts))
        paginator = Paginator(all_posts, 3)
        page = request.GET.get('page')

        try:
            posts = paginator.page(page)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        # lang_tags_blog_home = set(lang_tags_blog_home)
        # print(lang_tags)

        context['all_posts'] = all_posts
        context['posts'] = posts
        return context


class BlogPage(Page):
    parent_page_types = ['BlogHome']
    template = 'blog/blog_page.html'

    # header = StreamField([
    #     ('header', blocks.Header3Page())
    # ], null=True, max_num=1, use_json_field=True)

    # header_image = models.ForeignKey(
    #     'wagtailimages.Image', blank=True, null=True, on_delete=models.SET_NULL, related_name='+'
    # )
    # date = models.DateField("Post date")

    body = StreamField([
        ('content', home_blocks.BlogBlock()),
        ('bricks', home_blocks.BrickBlock()),
    ], use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel('body')
    ]

    # def get_context(self, request, *args, **kwargs):
    #     # Update context to include only published posts, ordered by reverse-chron
    #     context = super().get_context(request, *args, **kwargs)
    #
    #     # blogpages = self.get_children().live().order_by('-first_published_at')
    #     # all_posts = BlogPage.objects.live().public().order_by('-first_published_at')
    #
    #     all_posts = BlogPage.objects.live().public().order_by('-first_published_at').filter(locale__language_code='de')
    #
    #     all_posts = all_posts.exclude(pk=self.pk)
    #
    #     paginator = Paginator(all_posts, 3)
    #
    #     page = request.GET.get('page')
    #
    #     try:
    #         posts = paginator.page(page)
    #     except PageNotAnInteger:
    #         posts = paginator.page(1)
    #     except EmptyPage:
    #         posts = paginator.page(paginator.num_pages)
    #
    #     context['all_posts'] = all_posts
    #     context['posts'] = posts
    #     # context['blogpages'] = blogpages
    #     return context


class TravelBlogHome(Page):
    parent_page_types = ['home.HomePage']  # 'home.HomePage'
    template = 'blog/blog_home.html'

    # categories = ParentalManyToManyField('BlogCategory', blank=True, help_text='Welche Tags sollen in der Auswahl angezeigt werden?')

    body = StreamField([
        ('blog_cards', blog_blocks.BlogCardsBlock()),
    ], use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel('body')
    ]

    def get_context(self, request, *args, **kwargs):
        # Update context to include only published posts, ordered by reverse-chron
        context = super().get_context(request, *args, **kwargs)

        all_posts = TravelBlogPage.objects.live().public().order_by('-first_published_at')

        # random_sample = random.sample(list(all_posts), len(all_posts))
        paginator = Paginator(all_posts, 3)
        page = request.GET.get('page')

        try:
            posts = paginator.page(page)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        # lang_tags_blog_home = set(lang_tags_blog_home)
        # print(lang_tags)

        context['all_posts'] = all_posts
        context['posts'] = posts
        return context

class TravelBlogPage(Page):
    parent_page_types = ['TravelBlogHome']
    template = 'blog/blog_page.html'

    # header = StreamField([
    #     ('header', blocks.Header3Page())
    # ], null=True, max_num=1, use_json_field=True)

    # header_image = models.ForeignKey(
    #     'wagtailimages.Image', blank=True, null=True, on_delete=models.SET_NULL, related_name='+'
    # )
    # date = models.DateField("Post date")

    body = StreamField([
        ('content', home_blocks.BlogBlock()),
        ('bricks', home_blocks.BrickBlock()),
    ], use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel('body')
    ]

    # def get_context(self, request, *args, **kwargs):
    #     # Update context to include only published posts, ordered by reverse-chron
    #     context = super().get_context(request, *args, **kwargs)
    #
    #     # blogpages = self.get_children().live().order_by('-first_published_at')
    #     # all_posts = BlogPage.objects.live().public().order_by('-first_published_at')
    #
    #     all_posts = TravelBlogPage.objects.live().public().order_by('-first_published_at').filter(locale__language_code='de')
    #
    #     all_posts = all_posts.exclude(pk=self.pk)
    #
    #     paginator = Paginator(all_posts, 3)
    #
    #     page = request.GET.get('page')
    #
    #     try:
    #         posts = paginator.page(page)
    #     except PageNotAnInteger:
    #         posts = paginator.page(1)
    #     except EmptyPage:
    #         posts = paginator.page(paginator.num_pages)
    #
    #     context['all_posts'] = all_posts
    #     context['posts'] = posts
    #     # context['blogpages'] = blogpages
    #     return context