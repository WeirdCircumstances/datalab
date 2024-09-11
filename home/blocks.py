from wagtail import blocks
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from django.db import models


class HeroBlock(blocks.StructBlock):
    hero_list = blocks.ListBlock(
        blocks.StructBlock([
            ('image', ImageChooserBlock(blank=True, null=True, help_text='Bild')),
            ('text', blocks.RichTextBlock(default='Etwas Text, der in H1 über dem Bild angezeigt wird.')),
        ])
    )

    class Meta:
        icon = 'site'
        template = 'blocks/hero.html',
        label = 'Hero w/ 3 images'


class BlogContentBlock(blocks.StreamBlock):
    # heading = blocks.CharBlock(form_classname="full title", help_text="Überschrift")
    image = ImageChooserBlock()
    paragraph = blocks.RichTextBlock()
    button = blocks.ListBlock(
        blocks.StructBlock([
            ('link', blocks.PageChooserBlock(null=True)),
            ('text', blocks.CharBlock(null=True, default="Button Text")),
        ])
    )
    image_with_text = blocks.StructBlock([
        ('image', ImageChooserBlock(null=True)),
        ('text', blocks.CharBlock(null=True)),
    ])


class BlogBlock(blocks.StructBlock):
    title_image = ImageChooserBlock(required=True, help_text="Titelbild des Blogeintrags")
    title_text = blocks.CharBlock(required=True, help_text="Titel des Blogeintrags")
    content = BlogContentBlock(help_text="Inhalt des Blogeintrags")

    class Meta:
        icon = 'doc-full'
        label = 'Blogeintrag'
        template = 'blocks/blog.html'


class BrickBlock(blocks.StructBlock):
    header = blocks.CharBlock(required=True, null=True, default='Überschrift', help_text="Überschrift mit Biene")

    brick_list = blocks.ListBlock(
        blocks.StructBlock([
            # ('header', blocks.CharBlock(help_text="Titel des Bildes")),
            ('double', blocks.BooleanBlock(required=False, null=True, help_text='Das Bild in doppelter Breite anzeigen?')),
            ('cubic', blocks.BooleanBlock(required=False, null=True, help_text='Das Bild in groß als Quadrat anzeigen?')),
            ('image', ImageChooserBlock(blank=True, null=True, help_text='Bild')),
            ('text', blocks.RichTextBlock(null=True, required=False)),
        ])
    )

    class Meta:
        icon = 'doc-full'
        label = 'Bricks'
        template = 'blocks/brick.html'


class ParagraphBlock(blocks.StructBlock):
    paragraph = blocks.RichTextBlock(help_text='Textfeld für beliebigen Text',
                                     features=['h1', 'h2', 'h3', 'bold', 'italic', 'link', 'ol', 'ul', 'document-link', 'image', 'embed'])

    class Meta:
        icon = 'site'
        template = 'blocks/paragraph_block.html',
        label = 'Paragraph Block'


class ContactBlock(blocks.StructBlock):
    name_text = blocks.CharBlock(default='Name')
    name_placeholder = blocks.CharBlock(default='Name')
    email_text = blocks.CharBlock(default='E-Mail')
    email_placeholder = blocks.CharBlock(default='hello@mail.de')
    message_text = blocks.CharBlock(default='Nachricht')
    message_placeholder = blocks.CharBlock(default='Schreiben Sie mir!')
    send_button = blocks.CharBlock(default='Nachricht senden')
    thank_you_text = blocks.CharBlock(default='Die Nachricht wurde gesendet.')

    class Meta:
        icon = 'site'
        template = 'blocks/contact_block.html',
        label = 'Contact Block'


class BigImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(blank=True, null=True, help_text='Großes Bild, geeignet für den Beginn eines Blogeintrags')

    class Meta:
        icon = 'site'
        template = 'blocks/big_image.html',
        label = 'Big Image'


class INaturalistWidgetBlock(blocks.StructBlock):
    class Meta:
        icon = 'site'
        template = 'blocks/iNaturalist_widget.html',
        label = 'iNaturalist Widget'

# ToDo: CV Liste
