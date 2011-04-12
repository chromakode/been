from been.core import SiteFeedSource, source_registry

class GitHub(SiteFeedSource):
    URL_FORMAT = 'http://github.com/{username}.atom'
    kind = 'github'
    def __init__(self, config):
        SiteFeedSource.__init__(self, config)
        self.config['url'] = self.URL_FORMAT.format(username=self.config['username'])

    def process_event(self, event):
        event['summary'] = event['data']['title']
        return event

source_registry.add('github', GitHub)
