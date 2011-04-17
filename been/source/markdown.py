from been.core import DirectorySource, source_registry
import re
import unicodedata

def slugify(value):
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)

class MarkdownDirectory(DirectorySource):
    kind = 'markdown'
    def process_event(self, event):
        lines = event['content'].splitlines()
        event['title'] = lines[0]
        event['slug'] = slugify(event['title'])
        event['content'] = "\n".join(lines[1:])
        event['summary'] = event['content']
        return event
source_registry.add(MarkdownDirectory)
