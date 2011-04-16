from been.core import SiteFeedSource, source_registry

class Twitter(SiteFeedSource):
    url_format = 'http://api.twitter.com/1/statuses/user_timeline.atom?screen_name={username}'
    kind = 'twitter'
    def process_event(self, event):
        event['content'] = event['data']['content'][0]['value'].partition(': ')[2]
        event['summary'] = 'tweeted "'+event['content']+'"'
        return event
source_registry.add(Twitter)
