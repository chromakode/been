from hashlib import sha1
import feedparser
import markdown
import os
import re
import time
import unicodedata


def create_source(source_data):
    return source_map[source_data['kind']](source_data)


# slugify from Django source (BSD license)
def slugify(value):
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)


class Source(object):
    def __init__(self, config=None):
        self.config = config or {}
        self.config['kind'] = self.kind

    def fetch(self): raise NotImplementedError


class DirectorySource(Source):
    def fetch(self):
        path = self.config.get('path')
        events = []

        for filename in os.listdir(path):
            full_path = path + '/' + filename

            if not os.path.isfile(full_path):
                continue

            with open(full_path) as f:
                raw = f.read()

            event = {
                'filename'  : filename,
                'full_path' : full_path,
                'raw'       : raw,
                'timestamp' : time.gmtime(os.path.getmtime(full_path)),
            }

            event = self.process_event(event)

            if event:
                events.append(event)

        return events

    def process_event(self, event):
        return event

    @property
    def source_id(self):
        return self.kind+':'+self.config['path']

    @classmethod
    def configure(cls, path):
        return cls({'path':path.rstrip('/')})


class FeedSource(Source):
    def fetch(self):
        since = self.config.get('since', {})
        feed = feedparser.parse(self.config['url'],
                modified = time.gmtime(since['modified'])
                            if since.get('modified')
                            else None,
                etag = since.get('etag'))

        if feed.status == 304 or feed.status >= 400:
            return []
        else:
            events = []
            for entry in feed.entries:
                event = {
                    'author'     : entry.get('author'),
                    'summary'    : entry.get('title'),
                    'timestamp'  : entry.get('published_parsed') or entry.get('updated_parsed'),
                    'event_link' : entry.get('link'),
                    'data'       : entry
                }

                if 'content' in entry:
                    event['content'] = entry.get('content')[0]['value'],

                events.append(self.process_event(event))

            self.config['since'] = {'etag': feed.get('etag'), 'modified': feed.get('modified')}
            return events

    def process_event(self, event):
        return event


class SiteFeedSource(FeedSource):
    url_format = ''
    def __init__(self, config):
        FeedSource.__init__(self, config)
        self.config['url'] = self.url_format.format(username=self.config['username'])

    @property
    def source_id(self):
        return self.kind+':'+self.config['username']

    @classmethod
    def configure(cls, username):
        return cls({'username':username})


class DeliciousSource(SiteFeedSource):
    url_format = 'http://feeds.delicious.com/v2/rss/{username}?count=50'
    kind = 'delicious'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'bookmarked ' + event['data']['title']
        return event


class FanFictionSource(SiteFeedSource):
    url_format = 'http://b.fanfiction.net/atom/u/{username}/'
    kind = 'fanfiction'
    def process_event(self, event):
        event['summary'] = 'wrote a chapter in ' + event['data']['title']
        return event


class FlickrSource(SiteFeedSource):
    url_format = 'http://api.flickr.com/services/feeds/photos_public.gne?id={username}&lang=en-us&format=rss_200'
    kind = 'flickr'
    def process_event(self, event):
        event['summary'] = 'posted photo ' + event['data']['title']
        return event


class GitHubSource(SiteFeedSource):
    url_format = 'https://github.com/{username}.atom'
    kind = 'github'
    def process_event(self, event):
        summary = event['data']['title']
        if summary.startswith(self.config['username']):
            event['summary'] = summary[summary.find(' ') + 1:]
        return event


class GroovesharkSource(SiteFeedSource):
    url_format = 'http://api.grooveshark.com/feeds/1.0/users/{username}/recent_favorite_songs.rss'
    kind = 'grooveshark'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'favorited ' + event['data']['title']
        return event


class LastFMSource(SiteFeedSource):
    url_format = 'http://ws.audioscrobbler.com/2.0/user/{username}/recenttracks.rss?limit=50'
    kind = 'lastfm'
    def process_event(self, event):
        event['summary'] = 'listened to ' + event['data']['title']
        event['artist'], event['track'] = event['data']['title'].split(u' \u2013 ')
        return event


class MarkdownSource(DirectorySource):
    kind = 'markdown'
    def process_event(self, event):
        md = markdown.Markdown(extensions=['meta', 'tables', 'fenced_code', 'headerid'])
        event['content'] = md.convert(event['raw'])
        event['title'] = ' '.join(md.Meta.get('title', [event['filename']]))
        event['author'] = ' '.join(md.Meta.get('author', ['']))
        event['slug'] = '-'.join(md.Meta.get('slug', [slugify(event['title'])]))
        event['summary'] = 'posted ' + event['title']
        event['meta'] = md.Meta
        if md.Meta.get('published'):
            # Parse time, then convert struct_time (local) -> epoch (GMT) -> struct_time (GMT)
            event['timestamp'] = time.gmtime(time.mktime(time.strptime(' '.join(md.Meta.get('published')), '%Y-%m-%d %H:%M:%S')))
        event['_id'] = sha1(event['full_path'].encode('utf-8')).hexdigest()
        if time.gmtime() < event['timestamp']:
            return None
        else:
            return event


class RedditSource(SiteFeedSource):
    url_format = 'http://www.reddit.com/user/{username}/submitted/.rss'
    kind = 'reddit'
    def process_event(self, event):
        event['summary'] = 'submitted ' + event['data']['title']
        return event


class TwitterSource(SiteFeedSource):
    url_format = 'http://api.twitter.com/1/statuses/user_timeline.atom?screen_name={username}'
    kind = 'twitter'
    def process_event(self, event):
        event['content'] = event['data']['content'][0]['value'].partition(': ')[2]
        event['summary'] = 'tweeted "'+event['content']+'"'
        return event


source_map = {
    'delicious': DeliciousSource,
    'fanfiction': FanFictionSource,
    'flickr': FlickrSource,
    'github': GitHubSource,
    'grooveshark': GroovesharkSource,
    'lastfm': LastFMSource,
    'markdown': MarkdownSource,
    'reddit': RedditSource,
    'twitter': TwitterSource,
}
