from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class ParagraphBlock(blocks.StructBlock):
    paragraph = blocks.RichTextBlock(help_text='Textfeld für beliebigen Text',
                                     features=['h1', 'h2', 'h3', 'bold', 'italic', 'link', 'ol', 'ul', 'document-link', 'image', 'embed'], required=False)

    class Meta:
        icon = 'site'
        template = 'blocks/paragraph_block.html',
        label = 'Paragraph Block'


class StatisticsPlaceholderBlock(blocks.StructBlock):
    class Meta:
        icon = 'grip'
        template = 'blocks/statistics_placeholder.html',
        label = 'Ein Platzhalter für die einzubettenden Elemente'



# class GifBlock(blocks.StructBlock):
#     erfrischungskarte_gif = ImageChooserBlock()
#
#     class Meta:
#         icon = 'gif'
#         template = 'blocks/gif.html',
#         label = 'Gif Image Block'
