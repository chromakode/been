from been.core import SiteFeedSource, source_registry

class Reddit(SiteFeedSource):
    url_format = 'http://www.reddit.com/user/{username}/submitted/.rss'
    kind = 'reddit'
    def process_event(self, event):
        event['summary'] = 'submitted ' + event['data']['title']
        return event
source_registry.add(Reddit)
