from been.core import SiteFeedSource, source_registry

class FanFiction(SiteFeedSource):
    url_format = 'http://b.fanfiction.net/atom/u/{username}/'
    kind = 'fanfiction'
    def process_event(self, event):
        event['summary'] = 'wrote a chapter in ' + event['data']['title']
        return event
source_registry.add(FanFiction)
