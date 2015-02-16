'''
WikiLinks Extension for Python-Markdown
======================================

Converts [[WikiLinks]] to relative links.

See <https://pythonhosted.org/Markdown/extensions/wikilinks.html> 
for documentation.

Original code Copyright [Waylan Limberg](http://achinghead.com/).

All changes Copyright The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php) 

'''

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..inlinepatterns import Pattern
from ..util import etree
import re

import tornado.escape

def build_url(label, base, end):
    """ Build a url from the label, a base, and an end. """
    #clean_label = re.sub(r'([ ]+_)|(_[ ]+)|([ ]+)', '_', label)
    label2 = '#'.join(tornado.escape.url_escape(l) for l in label.split('#'))
    return '%s%s%s'% (base, label2, end)


class WikiLinkExtension(Extension):

    def __init__ (self, *args, **kwargs):
        self.config = {
            'base_url' : ['/', 'String to append to beginning or URL.'],
            'end_url' : ['/', 'String to append to end of URL.'],
            'html_class' : ['wikilink', 'CSS hook. Leave blank for none.'],
            'build_url' : [build_url, 'Callable formats URL from label.'],
            'titles' : [set(), 'Set of titles of known pages']
        }
        
        super(WikiLinkExtension, self).__init__(*args, **kwargs)
    
    def extendMarkdown(self, md, md_globals):
        self.md = md
    
        # append to end of inline patterns
#        WIKILINK_RE = r'\[\[([\w0-9_ -]+)\]\]'
        WIKILINK_RE = r'\[\[([^\]|]+)(\|([^\]]+))?\]\]'
        wikilinkPattern = WikiLinks(WIKILINK_RE, self.getConfigs())
        wikilinkPattern.md = md
        md.inlinePatterns.add('wikilink', wikilinkPattern, "<not_strong")


class WikiLinks(Pattern):
    def __init__(self, pattern, config):
        super(WikiLinks, self).__init__(pattern)
        self.config = config
  
    def handleMatch(self, m):
        if m.group(2).strip():
            base_url, end_url, html_class = self._getMeta()
            name = m.group(2).strip()
            label = m.group(4).strip() if m.group(4) else m.group(2).strip()
            url = self.config['build_url'](name, base_url, end_url)
            a = etree.Element('a')
            a.text = label
            a.set('href', url)
            a.set('id', 'link-' + name)

            names = self.config['titles']
            classes = []
            if name.lower() not in names :
                classes.append('wiki-noname')
            if html_class:
                classes.append(html_class)
            if classes :
                a.set('class', ' '.join(classes))

            if hasattr(self.md, 'Meta') :
                try :
                    links = self.md.Meta['wiki_links']
                except KeyError :
                    links = self.md.Meta['wiki_links'] = set()
                links.add(name.split('#')[0])
        else:
            a = ''
        return a

    def _getMeta(self):
        """ Return meta data or config data. """
        base_url = self.config['base_url']
        end_url = self.config['end_url']
        html_class = self.config['html_class']
        if hasattr(self.md, 'Meta'):
            if 'wiki_base_url' in self.md.Meta:
                base_url = self.md.Meta['wiki_base_url'][0]
            if 'wiki_end_url' in self.md.Meta:
                end_url = self.md.Meta['wiki_end_url'][0]
            if 'wiki_html_class' in self.md.Meta:
                html_class = self.md.Meta['wiki_html_class'][0]
        return base_url, end_url, html_class
    

def makeExtension(*args, **kwargs) :
    return WikiLinkExtension(*args, **kwargs)
