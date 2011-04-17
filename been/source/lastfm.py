from been.core import SiteFeedSource, source_registry

class LastFM(SiteFeedSource):
    url_format = 'http://ws.audioscrobbler.com/2.0/user/{username}/recenttracks.rss?limit=50'
    kind = 'lastfm'
    def process_event(self, event):
        event['summary'] = 'listened to ' + event['data']['title']
        event['artist'], event['track'] = event['data']['title'].split(u' \u2013 ')
        return event
source_registry.add(LastFM)
