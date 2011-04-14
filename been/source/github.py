from been.core import SiteFeedSource, source_registry

class GitHub(SiteFeedSource):
    url_format = 'https://github.com/{username}.atom'
    kind = 'github'
    def process_event(self, event):
        summary = event['summary']
        if summary.startswith(self.config['username']):
            event['summary'] = summary[summary.find(' ') + 1:]
        return event
source_registry.add(GitHub)
