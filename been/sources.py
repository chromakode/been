import os
import re
import subprocess
import time
import unicodedata
from hashlib import sha1

import feedparser
import markdown


source_map = {}


def source(name):
    def wrapper(cls):
        cls.kind = name
        source_map[name] = cls
        return cls
    return wrapper


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
    def _fetch_path(self, path):
        events = []

        for filename in os.listdir(path):
            full_path = os.path.join(path, filename)

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

    def fetch(self):
        return self._fetch_path(self.config['path'])

    def process_event(self, event):
        return event

    @property
    def source_id(self):
        return self.kind+':'+self.config['path']

    @classmethod
    def configure(cls, path):
        return cls({'path':path.rstrip('/')})


class GitDirectorySource(DirectorySource):
    def fetch(self):
        subprocess.check_call([
            'git',
            '-C', self.config['path'],
            'pull',
            '--quiet',
        ])

        events = self._fetch_path(os.path.join(
            self.config['path'],
            self.config['subdirectory'],
        ))

        # use the date of the first commit adding each file
        for event in events:
            output = subprocess.check_output([
                'git',
                '-C', self.config['path'],
                'log', '--follow', '--format=%at',
                event['full_path'],
            ])
            try:
                first_date = int(output.strip().split('\n')[-1])
            except ValueError:
                raise ValueError('invalid git log output for {!r}: {!r}'
                        .format(event['full_path'], output))
            event['timestamp'] = time.gmtime(first_date)

        return events


    @property
    def source_id(self):
        return self.kind+':'+self.config['path']+':'+self.config['subdirectory']

    @classmethod
    def configure(cls, path, subdirectory):
        return cls({
            'path': path.rstrip('/'),
            'subdirectory': subdirectory.strip('/'),
        })


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
                    'author': entry.get('author'),
                    'summary': entry.get('title'),
                    'timestamp': entry.get('published_parsed') or entry.get('updated_parsed'),
                    'event_link': entry.get('link'),
                    'data': entry,
                }

                if 'content' in entry:
                    event['content'] = entry.get('content')[0]['value'],

                event = self.process_event(event)
                if event:
                    events.append(event)

            self.config['since'] = {'etag': feed.get('etag'), 'modified': feed.get('modified_parsed') or feed.get('modified')}
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


@source('delicious')
class DeliciousSource(SiteFeedSource):
    url_format = 'http://feeds.delicious.com/v2/rss/{username}?count=50'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'bookmarked ' + event['data']['title']
        return event


@source('tumblr')
class TumblrSource(SiteFeedSource):
    url_format = 'http://{username}.tumblr.com/rss'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'posted ' + event['data']['title']
        return event


@source('fanfiction')
class FanFictionSource(SiteFeedSource):
    url_format = 'http://b.fanfiction.net/atom/u/{username}/'
    def process_event(self, event):
        event['summary'] = 'wrote a chapter in ' + event['data']['title']
        return event


@source('flickr')
class FlickrSource(SiteFeedSource):
    url_format = 'http://api.flickr.com/services/feeds/photos_public.gne?id={username}&lang=en-us&format=rss_200'
    def process_event(self, event):
        event['summary'] = 'posted photo ' + event['data']['title']
        return event


@source('github')
class GitHubSource(SiteFeedSource):
    url_format = 'https://github.com/{username}.atom'
    def process_event(self, event):
        summary = event['data']['title']
        if summary.startswith(self.config['username']):
            event['summary'] = summary[summary.find(' ') + 1:]
        return event


@source('grooveshark')
class GroovesharkSource(SiteFeedSource):
    url_format = 'http://api.grooveshark.com/feeds/1.0/users/{username}/recent_favorite_songs.rss'
    def process_event(self, event):
        event['author'] = self.config['username']
        event['summary'] = 'favorited ' + event['data']['title']
        return event


@source('lastfm')
class LastFMSource(SiteFeedSource):
    url_format = 'http://ws.audioscrobbler.com/2.0/user/{username}/recenttracks.rss?limit=50'
    def process_event(self, event):
        event['summary'] = 'listened to ' + event['data']['title']
        event['artist'], event['track'] = event['data']['title'].split(u' \u2013 ')
        return event


class MarkdownProcessor(object):
    def process_event(self, event):
        md = markdown.Markdown(extensions=['meta', 'tables', 'fenced_code', 'headerid'])
        event['content'] = md.convert(event['raw'])

        md_header = re.match(r'^#\w*(.*)\n', event['raw'])
        print md_header, event['raw']
        if md_header:
            event['title'] = md_header.group(1)
        elif 'title' in md.Meta:
            event['title'] = ' '.join(md.Meta['title'])
        else:
            filename = os.path.splitext(event['filename'])[0]
            event['title'] = filename

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


@source('markdown')
class MarkdownSource(MarkdownProcessor, DirectorySource):
    pass


@source('git-markdown')
class GitMarkdownSource(MarkdownProcessor, GitDirectorySource):
    pass


@source('reddit')
class RedditSource(SiteFeedSource):
    url_format = 'http://www.reddit.com/user/{username}/submitted/.rss'
    def process_event(self, event):
        event['summary'] = 'submitted ' + event['data']['title']
        return event


@source('twitter')
class TwitterSource(Source):

    def fetch(self):
        import twitter
        api = twitter.Api(
            consumer_key=self.config['consumer_key'],
            consumer_secret=self.config['consumer_secret'],
            access_token_key=self.config['access_token_key'],
            access_token_secret=self.config['access_token_secret'],
        )

        events = []
        keyword = self.config.get('keyword') and self.config['keyword'].lower()
        for tweet in api.GetUserTimeline(self.config['username']):
            event = {
                'author': tweet.user.screen_name,
                'timestamp': time.gmtime(tweet.created_at_in_seconds),
                'event_link': 'https://twitter.com/{user}/static/{id}'.format(
                    user=self.config['username'],
                    id=tweet.id,
                ),
                'content': tweet.text,
                'summary': u'tweeted "{tweet}"'.format(tweet=tweet.text),
            }
            if not keyword or keyword in event['content'].lower():
                events.append(event)
        return events

    @property
    def source_id(self):
        return self.kind+':'+self.config['username']

    @classmethod
    def configure(cls, consumer_key, consumer_secret, access_token_key,
                  access_token_secret, username, keyword=None):
        return cls({
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret,
            'access_token_key': access_token_key,
            'access_token_secret': access_token_secret,
            'username': username,
            'keyword': keyword
        })


@source('publish')
class PublishSource(Source):

    def __init__(self, config):
        Source.__init__(self, config)
        self.queue = []

    def publish(self, **kwargs):
        kwargs.setdefault('timestamp', time.time())
        kwargs.setdefault('summary', kwargs['content'])
        kwargs.update(self.config.get('default', {}))
        self.queue.append(kwargs)

    def fetch(self):
        events = self.queue
        self.queue = []
        return events

    @property
    def source_id(self):
        return self.kind+':'+self.config['name']

    @classmethod
    def configure(cls, name):
        return cls({'name':name})
