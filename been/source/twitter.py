from been.core import SiteFeedSource, source_registry

class Twitter(SiteFeedSource):
    URL_FORMAT = 'http://api.twitter.com/1/statuses/user_timeline.atom?screen_name={screen_name}'
    kind = 'twitter'
    def __init__(self, config):
        SiteFeedSource.__init__(self, config)
        self.config['url'] = self.URL_FORMAT.format(screen_name=self.config['username'])

    def process_event(self, event):
        status = event['data']['content'][0]['value'].partition(': ')[2]
        event['summary'] = 'tweeted <q>'+status+'</q>'
        return event

source_registry.add('twitter', Twitter)
