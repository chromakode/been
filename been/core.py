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

    def fetch(self): raise NotImplementedError

class FeedSource(Source):
    def fetch(self):
        since = self.config.get('since', {})
        modified = time.gmtime(since.get('modified'))
        feed = feedparser.parse(self.config['url'],
                modified = time.gmtime(since['modified'])
                            if since.get('modified')
                            else None,
                etag = since.get('etag'))

        if feed.status == 304:
            return []
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
            
            self.config['since'] = {'etag': feed.get('etag'), 'modified': feed.get('modified')}
            return events

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
                    groups[source] = {
                        "source": source,
                        "kind": event["kind"],
                        "timestamp": event["timestamp"],
                        "children": []
                    }
                group = groups[source]
                latest = group["children"][-1]['timestamp'] if group["children"] else event['timestamp']

                # Group if the event occured within "interval" (default 2 hours) of
                # the last of the same source.
                interval = collapse.get('interval', 2*60*60)
                # Compare latest - current, since events are ordered descending by timestamp.
                if group['timestamp'] - event['timestamp'] <= interval:
                    group["children"].append(event)
                    group["timestamp"] = event["timestamp"]
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
        self.sources = {}
    
    def init(self):
        import couch
        self.store = couch.CouchStore().load()
        for source_id, source_data in self.store.get_sources().iteritems():
            self.sources[source_id] = source_registry.create(source_data)
        return self

    def add(self, source):
        self.sources[source.source_id] = source
        self.store.store_source(source)

    def update(self):
        for source in self.sources.itervalues():
            self.store.store_update(source, source.fetch())

    def reprocess(self):
        def reprocess_iter():
            for event in self.store.events():
                yield self.sources[event['source']].process_event(event)
        self.store.store_events(list(reprocess_iter()))
