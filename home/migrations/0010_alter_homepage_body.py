# Generated by Django 5.0.6 on 2024-05-30 21:13

import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0009_alter_homepage_body'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homepage',
            name='body',
            field=wagtail.fields.StreamField([('blog_entry', wagtail.blocks.StructBlock([('title_text', wagtail.blocks.CharBlock(help_text='Titel des Blogeintrags', required=True)), ('title_image', wagtail.images.blocks.ImageChooserBlock(help_text='Titelbild des Blogeintrags', required=True)), ('content', wagtail.blocks.StreamBlock([('paragraph', wagtail.blocks.RichTextBlock()), ('image', wagtail.images.blocks.ImageChooserBlock())], help_text='Inhalt des Blogeintrags'))]))], default=None),
        ),
    ]
