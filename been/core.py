import time
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
        modified = time.gmtime(since.get('modified'))
        feed = feedparser.parse(self.config['url'],
                modified = time.gmtime(since['modified'])
                            if since.get('modified')
                            else None,
                etag = since.get('etag'))

        if feed.status == 304:
            return [], since
        else:
            events = []
            for entry in feed.entries:
                event = {
                    'author'     : entry.get('author'),
                    'summary'    : entry.get('title'),
                    'timestamp'  : entry.get('published_parsed') or entry.get('updated_parsed'),
                    'event_link' : entry.get('link'),
                    'data'       : entry
                }

                if 'content' in entry:
                    event['content'] = entry.get('content')[0]['value'],

                events.append(self.process_event(event))
            
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
    
    def collapsed_events(self, *args, **kwargs):
        groups = {}
        sources = self.get_sources()
        for event in self.events(*args, **kwargs):
            source = event['source']
            collapse = sources[source].get('collapse', {})
            if collapse == True: collapse = {}

            # Group if the source or the event has a "collapse" property set.
            if sources[source].get('collapse') or event.get('collapse'):
                if source not in groups:
                    groups[source] = {"source":source, "kind":event["kind"], "children":[]}
                group = groups.setdefault(source, [])
                latest = group["children"][-1]['timestamp'] if group["children"] else event['timestamp']

                # Group if the event occured within "interval" (default 2 hours) of
                # the last of the same source.
                interval = collapse.get('interval', 2*60*60)
                if latest - event['timestamp'] <= interval:
                    group["children"].append(event)
                else:
                    # If a longer interval occurred, empty and yield the group.
                    del groups[source]
                    yield group
            else:
                yield event

        # Yield any remaining groups.
        for group in groups.itervalues():
            yield group

class Been(object):
    def __init__(self):
        self.sources = []
    
    def init(self):
        import couch
        self.store = couch.CouchStore().load()
        for source_data in self.store.get_sources().itervalues():
            self.sources.append(source_registry.create(source_data))
        return self

    def add(self, source):
        self.sources.append(source)
        self.store.add_source(source)

    def update(self):
        for source in self.sources:
            self.store.update(source)
