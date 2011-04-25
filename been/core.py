import time
import feedparser
import os

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

class DirectorySource(Source):
    def fetch(self):
        path = self.config.get('path')
        events = []

        for filename in os.listdir(path):
            full_path = path + '/' + filename

            if not os.path.isfile(full_path):
                continue

            with open(full_path) as f:
                raw = f.read()

            event = {
                'filename'  : filename,
                'full_path' : full_path,
                'raw'       : raw,
                'timestamp' : time.gmtime(os.path.getmtime(full_path)),
            }

            event = self.process_event(event)

            if event:
                events.append(event)

        return events

    def process_event(self, event):
        return event

    @property
    def source_id(self):
        return self.kind+':'+self.config['path']

    @classmethod
    def configure(cls, path):
        return cls({'path':path.rstrip('/')})

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
        events = list(self.events(*args, **kwargs))
        for index, event in enumerate(events):
            source = event['source']
            collapse = sources[source].get('collapse', False)
            if collapse == True: collapse = {}

            # Group if the source or the event has a "collapse" property set.
            if collapse != False or event.get('collapse'):
                def group_event():
                    if source not in groups:
                        groups[source] = {
                            "source": source,
                            "kind": event["kind"],
                            "timestamp": event["timestamp"],
                            "children": []
                        }
                    group = groups[source]

                    # Group if the event occured within "interval" (default 2 hours) of
                    # the last of the same source.
                    latest = group["children"][-1]['timestamp'] if group["children"] else event['timestamp']
                    interval = collapse.get('interval', 2*60*60)
                    # Compare latest - current, since events are ordered descending by timestamp.
                    if group['timestamp'] - event['timestamp'] <= interval:
                        event["collapsed"] = True
                        group["children"].append(event)
                        group["timestamp"] = event["timestamp"]
                        group["index"] = index
                    else:
                        # If a longer interval occurred, empty the group and add it at the position of its last event.
                        events[group["index"]] = group
                        del group["index"]
                        del groups[source]
                        # Add this event to a new group by processing it again (with the cleared group).
                        group_event()
                group_event()

        return filter(lambda e:not e.get("collapsed"), events)

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

    def update(self, sources=None):
        sources = sources or self.sources.itervalues()
        for source in sources:
            self.store.store_update(source, source.fetch())

    def reprocess(self):
        def reprocess_iter():
            for event in self.store.events():
                yield self.sources[event['source']].process_event(event)
        self.store.store_events(list(reprocess_iter()))
