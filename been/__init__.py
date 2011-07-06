import os
from been.stores import create_store
from been.sources import create_source

class Been(object):
    def __init__(self):
        self.sources = {}

        engine = os.environ.get('BEEN_STORE', 'couch')
        self.store = create_store(engine)

        for source_id, source_data in self.store.get_sources().iteritems():
            self.sources[source_id] = create_source(source_data)

    def add(self, source):
        self.sources[source.source_id] = source
        self.store.store_source(source)

    def update(self, sources=None):
        sources = sources or self.sources.itervalues()
        changed = {}
        for source in sources:
            changed[source.source_id] = self.store.store_update(source, source.fetch())
        return changed

    def reprocess(self):
        def reprocess_iter():
            for event in self.store.events():
                yield self.sources[event['source']].process_event(event)
        self.store.store_events(list(reprocess_iter()))
