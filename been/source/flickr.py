from been.core import SiteFeedSource, source_registry

class Flickr(SiteFeedSource):
    url_format = 'http://api.flickr.com/services/feeds/photos_public.gne?id={username}&lang=en-us&format=rss_200'
    kind = 'flickr'
    def process_event(self, event):
        event['summary'] = 'posted photo ' + event['summary']
        event['collapse'] = True
        return event
source_registry.add(Flickr)
