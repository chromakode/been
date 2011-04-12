from been.core import SiteFeedSource, source_registry

class GitHub(SiteFeedSource):
    url_format = 'http://github.com/{username}.atom'
    kind = 'github'
source_registry.add(GitHub)
