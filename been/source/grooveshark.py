from been.core import SiteFeedSource, source_registry

class Grooveshark(SiteFeedSource):
    url_format = 'http://api.grooveshark.com/feeds/1.0/users/{username}/recent_favorite_songs.rss'
    kind = 'grooveshark'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'favorited ' + event['summary']
        return event
source_registry.add(Grooveshark)
