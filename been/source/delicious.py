from been.core import SiteFeedSource, source_registry

class Delicious(SiteFeedSource):
    url_format = 'http://feeds.delicious.com/v2/rss/{username}?count=50'
    kind = 'delicious'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'bookmarked ' + event['summary']
        return event
source_registry.add(Delicious)
