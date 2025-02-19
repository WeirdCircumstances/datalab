# Generated by Django 5.0.7 on 2024-07-24 11:54

import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0027_alter_homepage_body_alter_impressumpage_body'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gallerypage',
            name='body',
            field=wagtail.fields.StreamField([('bricks', wagtail.blocks.StructBlock([('header', wagtail.blocks.CharBlock(default='Überschrift', help_text='Überschrift mit Biene', null=True, required=True)), ('brick_list', wagtail.blocks.ListBlock(wagtail.blocks.StructBlock([('double', wagtail.blocks.BooleanBlock(help_text='Das Bild in doppelter Breite anzeigen?', null=True, required=False)), ('cubic', wagtail.blocks.BooleanBlock(help_text='Das Bild in groß als Quadrat anzeigen?', null=True, required=False)), ('image', wagtail.images.blocks.ImageChooserBlock(blank=True, help_text='Bild', null=True)), ('text', wagtail.blocks.RichTextBlock(null=True, required=False))])))])), ('iNaturalist', wagtail.blocks.StructBlock([]))], default=None),
        ),
    ]
