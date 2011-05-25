from hashlib import sha1
import time
import calendar
import couchdb
from core import Store

def dates_to_epoch(d):
    for key, value in d.iteritems():
        if hasattr(value, "iteritems"):
            d[key] = dates_to_epoch(value)
        elif type(value) is time.struct_time:
            d[key] = calendar.timegm(value)
    return d

class CouchStore(Store):
    def load(self):
        self.server = couchdb.client.Server()

        db_name = self.config.get('db_name', 'activity')
        if not db_name in self.server:
            self.server.create(db_name)
        self.db = self.server[db_name]
        self.init_views()

        return self

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
        options = { 'limit': count, 'descending': descending }
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
