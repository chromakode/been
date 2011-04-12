from hashlib import sha1
import couchdb
from core import Store

# Add time serialization to couchdb's json repertoire.
import json
import time
class TimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is time.struct_time:
            return time.mktime(obj)
        else:
            return json.JSONEncoder.default(self, obj)
couchdb.json.use(
        decode=json.JSONDecoder().decode,
        encode=TimeEncoder().encode)

class CouchStore(Store):
    def load(self):
        self.server = couchdb.client.Server()

        db_name = self.config.get('db_name', 'activity')
        if not db_name in self.server:
            self.server.create(db_name)
        self.db = self.server[db_name]
        self.init_views()

        return self.get_sources()

    def init_views(self):
        if '_design/activity' not in self.db:
            self.db['_design/activity'] = {
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
                       }
                   }
                }

    def get_sources(self):
        return self.db.view('activity/sources')

    def add_source(self, source):
        source_data = source.config.copy()
        source_data['type'] = 'source'
        self.db[source.source_id] = source_data

    def update(self, source):
        source_info = self.db[source.source_id]

        events, since = source.fetch(source_info.get('since', {}))
        for event in events:
            event['_id'] = sha1(event['summary'].encode('utf-8')+str(event['timestamp'])).hexdigest()
            event['type'] = 'event'
            event['source'] = source.source_id
        self.db.update(events)

        source_info['since'] = since
        self.db[source.source_id] = source_info

    def events(self, count=100):
        return (event.value for event in self.db.view('activity/events', limit=count, descending=True))

    def empty(self):
        for event in self.db.view('activity/events'):
            self.db.delete(event.value)
