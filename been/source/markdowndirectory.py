from been.core import DirectorySource, source_registry
from hashlib import sha1
import re
import unicodedata
import time
import markdown

# slugify from Django source (BSD license)
def slugify(value):
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)

class MarkdownDirectory(DirectorySource):
    kind = 'markdown'
    def process_event(self, event):
        md = markdown.Markdown(extensions=['meta', 'tables', 'fenced_code', 'headerid'])
        event['content'] = md.convert(event['raw'])
        event['title'] = ' '.join(md.Meta.get('title', [event['filename']]))
        event['author'] = ' '.join(md.Meta.get('author', ['']))
        event['slug'] = '-'.join(md.Meta.get('slug', [slugify(event['title'])]))
        event['summary'] = ' '.join(md.Meta.get('summary', [event['raw'][:100]]))
        if md.Meta.get('published'):
            # Parse time, then convert struct_time (local) -> epoch (GMT) -> struct_time (GMT)
            event['timestamp'] = time.gmtime(time.mktime(time.strptime(' '.join(md.Meta.get('published')), '%Y-%m-%d %H:%M:%S')))
        event['_id'] = sha1(event['full_path'].encode('utf-8')).hexdigest()
        if time.gmtime() < event['timestamp']:
            return None
        else:
            return event
source_registry.add(MarkdownDirectory)
