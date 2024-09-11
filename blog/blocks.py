from wagtail import blocks

class BlogCardsBlock(blocks.StructBlock):
    """
    Blog Home near end of page
    """

    class Meta:
        icon = 'grip'
        template = 'blog/blog_cards.html',
        label = 'Blog Cards - Karten mit kleiner Animation, unten auf der Seite'