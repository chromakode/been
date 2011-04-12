import pkgutil
import feedparser

class SourceRegistry(dict):
    def add(self, cls):
        self[cls.kind] = cls

    def create(self, data):
        return self[data['kind']](data)

source_registry = SourceRegistry()

class Source(object):
    def __init__(self, config=None):
        self.config = config or {}
        self.config['kind'] = self.kind

    def fetch(self, since): raise NotImplementedError

class FeedSource(Source):
    def fetch(self, since):
        feed = feedparser.parse(self.config['url'],
                modified=since.get('modified'),
                etag=since.get('etag'))
        events = []

        for entry in feed.entries:
            events.append(self.process_event({
                'author'     : entry.get('author'),
                'summary'    : entry.get('title'),
                'content'    : entry.get('content')[0]['value'],
                'timestamp'  : entry.get('published_parsed'),
                'event_link' : entry.get('link'),
                'data'       : entry
            }))
        
        since = {'etag': feed.get('etag'), 'modified': feed.get('modified')}
        return events, since

    def process_event(self, event):
        return event

class SiteFeedSource(FeedSource):
    url_format = ''
    def __init__(self, config):
        FeedSource.__init__(self, config)
        self.config['url'] = self.url_format.format(username=self.config['username'])

    @property
    def source_id(self):
        return self.kind+':'+self.config['username']

    @classmethod
    def configure(cls, username):
        return cls({'username':username})

class Store(object):
    def __init__(self, config=None):
        self.config = config or {}

    def update(self, source): raise NotImplementedError

class Been(object):
    def __init__(self):
        self.sources = []
    
    def init(self):
        import couch
        self.store = couch.CouchStore()
        for source_data in self.store.load():
            self.sources.append(source_registry.create(source_data.value))

    def add(self, source):
        self.sources.append(source)
        self.store.add_source(source)

    def update(self):
        for source in self.sources:
            self.store.update(source)
