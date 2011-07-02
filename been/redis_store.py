from hashlib import sha1
import time
import redis
import pickle
from core import Store

def dates_to_epoch(d):
    for key, value in d.iteritems():
        if hasattr(value, 'iteritems'):
            d[key] = dates_to_epoch(value)
        elif type(value) is time.struct_time:
            d[key] = int(time.mktime(value))
    return d

def unpickle_dict(dict_):
    """Converts a dict of pickled items to a dict of unpickled items."""
    return dict((k, pickle.loads(v)) for k, v in dict_.iteritems())

class RedisStore(Store):
    def load(self):
        self.db = redis.Redis()
        return self

    def get_sources(self):
        return unpickle_dict(self.db.hgetall('sources'))

    def get_source_ids(self):
        return self.db.hkeys('sources')

    def store_source(self, source):
        source_data = source.config.copy()
        dates_to_epoch(source_data)
        self.db.hset('sources', source.source_id, pickle.dumps(source_data))

    def store_events(self, events):
        ids = {}
        for event in events:
            dates_to_epoch(event)
            event.setdefault('_id', sha1(event['summary'].encode('utf-8')+str(event['timestamp'])).hexdigest())

            pipe = self.db.pipeline(transaction=True)
            pipe.hset('events', event['_id'], pickle.dumps(event))
            # Uggghhhh, the zadd API is terrible!
            pipe.zadd('events-by-timestamp', **{event['_id']: event['timestamp']})
            pipe.zadd('events-by-source:' + event['source'], **{event['_id']: event['timestamp']})
            if event.get('slug'):
                pipe.hset('events-by-slug', event['slug'], event['_id'])
            pipe.execute()

        return len(events)

    def store_update(self, source, events):
        for event in events:
            event['kind'] = source.kind
            event['source'] = source.source_id
        self.store_source(source)
        return self.store_events(events)

    def events(self, count=100, before=None, source=None, descending=True):
        key = 'events-by-timestamp'
        start = int(time.mktime(time.gmtime()))

        if source is not None:
            key = 'events-by-source:' + source
        elif before is not None:
            start = int(before)

        query = self.db.zrevrangebyscore if descending else self.db.zrangebyscore

        return self.events_by_ids(query(key, start, '-inf', start=0, num=count))

    def event_by_id(self, id):
        return pickle.loads(self.db.hget('events', id))

    def events_by_ids(self, ids):
        if not ids:
            return []
        return (pickle.loads(p) for p in self.db.hmget('events', ids))

    def events_by_slug(self, slug):
        id = self.db.hget('events-by-slug', slug)
        return [self.event_by_id(id)] if id is not None else []

    def events_by_source_count(self):
        return dict((source_id, self.db.hlen('events-by-source:' + source_id)) for source_id in self.get_source_ids())

    def empty(self):
        pipe = self.db.pipeline(transaction=True)
        pipe.delete(
            'events',
            'events-by-timestamp',
            'events-by-slug',
            *('events-by-source:' + source_id for source_id in self.get_source_ids())
        )
        pipe.execute()

        sources = self.get_sources()
        if sources:
            for source_id in sources:
                sources[source_id]['since'] = {}
                sources[source_id] = pickle.dumps(sources[source_id])
            self.db.hmset('sources', sources)
