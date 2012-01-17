from hashlib import sha1
import time
import calendar
import pickle
import couchdb
import redis


def create_store(name):
    return store_map[name]()


def dates_to_epoch(d):
    """Recursively converts all dict values that are struct_times to Unix timestamps."""
    for key, value in d.iteritems():
        if hasattr(value, 'iteritems'):
            d[key] = dates_to_epoch(value)
        elif type(value) is time.struct_time:
            d[key] = int(calendar.timegm(value))
    return d


def unpickle_dict(dict_):
    """Accepts a dict of pickled items and returns a dict of unpickled items."""
    return dict((k, pickle.loads(v)) for k, v in dict_.iteritems())


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
                            "index": index,
                            "children": []
                        }
                    group = groups[source]

                    # Group if the event occured within "interval" (default 2 hours) of
                    # the last of the same source.
                    latest = group['timestamp'] if group["children"] else event['timestamp']
                    interval = collapse.get('interval', 2*60*60)
                    # Compare latest - current, since events are ordered descending by timestamp.
                    if group['timestamp'] - event['timestamp'] <= interval:
                        event["collapsed"] = True
                        group["children"].append(event)
                    else:
                        # If a longer interval occurred, empty the group and add it at the position of its last event.
                        events[group["index"]] = group
                        del group["index"]
                        del groups[source]
                        # Add this event to a new group by processing it again (with the cleared group).
                        group_event()
                group_event()

        return filter(lambda e:not e.get("collapsed"), events)


class CouchStore(Store):
    def __init__(self):
        super(CouchStore, self).__init__()
        self.server = couchdb.client.Server()

        db_name = self.config.get('db_name', 'activity')
        if not db_name in self.server:
            self.server.create(db_name)
        self.db = self.server[db_name]
        self.init_views()

    def init_views(self):
        views = {
            "_id": "_design/activity",
            "language": "javascript",
            "views": {
                "sources": {
                    "map": "function(doc) { if (doc.type == 'source') { emit(doc._id, doc) } }"
                },
                "events": {
                    "map": "function(doc) { if (doc.type == 'event') { emit(doc.timestamp, doc) } }"
                },
                "events-by-source": {
                    "map": "function(doc) { if (doc.type == 'event') { emit(doc.source, doc) } }"
                },
                "events-by-source-count": {
                    "map": "function(doc) { if (doc.type == 'event') { emit(doc.source, doc) } }",
                    "reduce": "_count"
                },
                "events-by-slug": {
                    "map": "function(doc) { if (doc.type == 'event' && doc.slug) { emit(doc.slug, doc) } }"
                }
            }
        }
        doc = self.db.get(views['_id'], {})
        doc.update(views)
        self.db[views['_id']] = doc

    def get_sources(self):
        return dict((row.key, row.value) for row in self.db.view('activity/sources'))

    def store_source(self, source):
        source_data = source.config.copy()
        source_data['type'] = 'source'
        dates_to_epoch(source_data)
        if source.source_id not in self.db or self.db[source.source_id] != source_data:
            self.db[source.source_id] = dates_to_epoch(source_data)

    def store_events(self, events):
        ids = {}
        changed = 0
        for event in events:
            dates_to_epoch(event)
            event.setdefault('_id', sha1(event['summary'].encode('utf-8')+str(event['timestamp'])).hexdigest())
            ids[event['_id']] = event
            event['type'] = 'event'

        tries = 3
        while ids and tries:
            tries -= 1
            result = self.db.update(ids.values())
            for success, _id, info in result:
                if success:
                    del ids[_id]
                    changed += 1
                else:
                    cur = self.db[_id]
                    ids[_id]['_rev'] = cur['_rev']
                    if cur == ids[_id]:
                        # If the data is the same, skip creating a new revision.
                        del ids[_id]

        if ids:
            raise couchdb.ResourceConflict

        return changed

    def store_update(self, source, events):
        for event in events:
            event['kind'] = source.kind
            event['source'] = source.source_id
        self.store_source(source)
        return self.store_events(events)

    def events(self, count=100, before=None, source=None, descending=True):
        options = { 'descending': descending }
        if count is not None:
            options['limit'] = count

        view = 'activity/events'

        if source is not None:
            options['startkey'] = source
            view = 'activity/events-by-source'
        elif before is not None:
            options['startkey'] = before

        return (event.value for event in self.db.view(view, **options))

    def events_by_slug(self, slug):
        return (event.value for event in self.db.view('activity/events-by-slug')[slug])

    def events_by_source_count(self):
        return dict((count.key, count.value) for count in self.db.view('activity/events-by-source-count', group_level=1))

    def empty(self):
        for event in self.db.view('activity/events'):
            self.db.delete(event.value)
        for row in self.db.view('activity/sources'):
            source = row.value
            source['since'] = {}
            self.db[row.id] = source


class RedisStore(Store):
    def __init__(self):
        super(RedisStore, self).__init__()
        self.db = redis.Redis()
        self.prefix = 'activity-'

    def get_sources(self):
        return unpickle_dict(self.db.hgetall(self.prefix + 'sources'))

    def get_source_ids(self):
        return self.db.hkeys(self.prefix + 'sources')

    def store_source(self, source):
        source_data = source.config.copy()
        dates_to_epoch(source_data)
        self.db.hset(self.prefix + 'sources', source.source_id, pickle.dumps(source_data))

    def store_events(self, events):
        ids = {}
        for event in events:
            dates_to_epoch(event)
            event.setdefault('_id', sha1(event['summary'].encode('utf-8')+str(event['timestamp'])).hexdigest())

            pipe = self.db.pipeline(transaction=True)
            pipe.hset(self.prefix + 'events', event['_id'], pickle.dumps(event))
            # Uggghhhh, the zadd API is terrible!
            pipe.zadd(self.prefix + 'events-by-timestamp', **{event['_id']: event['timestamp']})
            pipe.zadd(self.prefix + 'events-by-source:' + event['source'], **{event['_id']: event['timestamp']})
            if event.get('slug'):
                pipe.hset(self.prefix + 'events-by-slug', event['slug'], event['_id'])
            pipe.execute()

        return len(events)

    def store_update(self, source, events):
        for event in events:
            event['kind'] = source.kind
            event['source'] = source.source_id
        self.store_source(source)
        return self.store_events(events)

    def events(self, count=100, before=None, source=None, descending=True):
        key = self.prefix + 'events-by-timestamp'
        start = int(time.mktime(time.gmtime()))

        if source is not None:
            key = self.prefix + 'events-by-source:' + source
        elif before is not None:
            start = int(before)

        query = self.db.zrevrangebyscore if descending else self.db.zrangebyscore

        return self.events_by_ids(query(key, start, '-inf', start=0, num=count))

    def event_by_id(self, id):
        return pickle.loads(self.db.hget(self.prefix + 'events', id))

    def events_by_ids(self, ids):
        if not ids:
            return []
        return (pickle.loads(p) for p in self.db.hmget(self.prefix + 'events', ids))

    def events_by_slug(self, slug):
        id = self.db.hget(self.prefix + 'events-by-slug', slug)
        return [self.event_by_id(id)] if id is not None else []

    def events_by_source_count(self):
        return dict((source_id, self.db.zcard(self.prefix + 'events-by-source:' + source_id)) for source_id in self.get_source_ids())

    def empty(self):
        pipe = self.db.pipeline(transaction=True)
        pipe.delete(
            self.prefix + 'events',
            self.prefix + 'events-by-timestamp',
            self.prefix + 'events-by-slug',
            *(self.prefix + 'events-by-source:' + source_id for source_id in self.get_source_ids())
        )
        pipe.execute()

        sources = self.get_sources()
        if sources:
            for source_id in sources:
                sources[source_id]['since'] = {}
                sources[source_id] = pickle.dumps(sources[source_id])
            self.db.hmset(self.prefix + 'sources', sources)

store_map = {
    'couch': CouchStore,
    'redis': RedisStore,
}
