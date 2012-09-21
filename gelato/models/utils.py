import html5lib
from html5lib.serializer.htmlserializer import HTMLSerializer
import jingo
import jinja2

from django.utils.encoding import smart_unicode


def clean_nl(string):
    """
    This will clean up newlines so that nl2br can properly be called on the
    cleaned text.
    """

    html_blocks = ['blockquote', 'ol', 'li', 'ul']

    if not string:
        return string

    def parse_html(tree):
        prev_tag = ''
        for i, node in enumerate(tree.childNodes):
            if node.type == 4:  # Text node
                value = node.value

                # Strip new lines directly inside block level elements.
                if node.parent.name in html_blocks:
                    value = value.strip('\n')

                # Remove the first new line after a block level element.
                if (prev_tag in html_blocks and value.startswith('\n')):
                    value = value[1:]

                tree.childNodes[i].value = value
            else:
                tree.insertBefore(parse_html(node), node)
                tree.removeChild(node)

            prev_tag = node.name
        return tree

    parse = parse_html(html5lib.parseFragment(string))

    walker = html5lib.treewalkers.getTreeWalker('simpletree')
    stream = walker(parse)
    serializer = HTMLSerializer(quote_attr_values=True,
                                omit_optional_tags=False)
    return serializer.render(stream)


@jingo.register.filter
def truncate(s, length=255, killwords=True, end='...'):
    """
    Wrapper for jinja's truncate that checks if the object has a
    __truncate__ attribute first.

    Altering the jinja2 default of killwords=False because of
    https://bugzilla.mozilla.org/show_bug.cgi?id=624642, which could occur
    elsewhere.
    """
    if s is None:
        return ''
    if hasattr(s, '__truncate__'):
        return s.__truncate__(length, killwords, end)
    return jinja2.filters.do_truncate(smart_unicode(s), length, killwords, end)


