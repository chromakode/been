from been.core import SiteFeedSource, source_registry

class LastFM(SiteFeedSource):
    url_format = 'http://ws.audioscrobbler.com/2.0/user/{username}/recenttracks.rss?limit=50'
    kind = 'lastfm'
source_registry.add(LastFM)
