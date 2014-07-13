#!/usr/bin/env python
import sys
import json
import time
from been import Been
from been.stores import create_store, store_map
from been.sources import source_map

_cmds = {}
def command(name=None):
    def wrapper(f):
        _cmds[name or f.func_name] = f
        return f
    return wrapper


def run_command(cmd, app, args):
    disambiguate(cmd, _cmds, 'command')(app, *args)


def disambiguate(key, dict_, desc='key'):
    try:
        item = dict_[key]
    except KeyError:
        matches = [m for m in dict_.iterkeys() if m.startswith(key)]
        if len(matches) == 0:
            print 'No {desc} matching \'{key}\''.format(desc=desc, key=key)
            sys.exit(1)
        elif len(matches) > 1:
            print 'Ambiguous {desc} \'{key}\':'.format(desc=desc, key=key)
            for match_id in sorted(matches):
                print '   ' + match_id
            sys.exit(1)
        else:
            item = dict_[matches[0]]
    return item


@command()
def update(app, source_id=None):
    """update (source_id): Fetches events from all sources. If (source_id) is specified, updates a single source."""
    if source_id:
        source = disambiguate(source_id, app.sources, 'source')
        changed = app.update([source])
    else:
        changed = app.update()

    print '{ts} -- +{total} events [{changes}]'.format(
            ts = time.ctime(),
            total = sum(changed.itervalues()),
            changes = ', '.join('{0}(+{1})'.format(_id, count) for _id, count in changed.iteritems()))


@command()
def add(app, kind=None, *args):
    """add <kind> (parameters): Registers a source of the specified <kind>."""
    source_cls = source_map.get(kind)
    if not source_cls:
        if kind is not None:
            print "Invalid source kind '{kind}' specified.".format(kind=kind)
        else:
            print add.__doc__
        print "Available source kinds:"
        for kind in source_map:
            print "  " + kind
        sys.exit(1)

    source = source_cls.configure(*args)

    if source.source_id in app.sources:
        print "A source with id '{id} already exists.'".format(id=source.source_id)
        return

    app.add(source)


@command()
def log(app):
    """log: Displays summaries for the 100 newest events."""
    for event in app.store.events():
        print event['summary'].encode('utf-8')


@command(name='list')
def list_(app, format=None):
    """list (format): Displays the IDs of all registered sources. Available formats: short"""
    counts = app.store.events_by_source_count()
    for source_id, source in app.sources.iteritems():
        print '{name}'.format(name = source_id)
        if not format == 'short':
            print '  {0} events'.format(counts.get(source_id, 0))
            for field in ['username', 'url', 'collapse', 'syndicate']:
                if field in source.config:
                    print '  * {0}: {1}'.format(field, source.config[field])


@command()
def empty(app):
    """empty: Clears the event store of all events."""
    app.store.empty()


@command()
def reprocess(app):
    """reprocess: Reprocesses events using their stored data."""
    app.reprocess()


@command()
def configure(app, source_id, key, *args):
    """configure <source> <key> (value): Get or set the value of <key> for <source>."""
    source = disambiguate(source_id, app.sources, 'source')
    if args:
        value = ' '.join(args)
        try:
            value = json.loads(value)
        except ValueError:
            pass
        source.config[key] = value
        app.store.store_source(source)
    else:
        print json.dumps(source.config.get(key))


@command()
def migrate(app, from_store, to_store):
    """migrate <from> <to>: copies your source/event storage from one backend to another."""

    bad_store = None

    if not to_store in store_map:
        bad_store = to_store

    if not from_store in store_map:
        bad_store = from_store

    if bad_store:
        print "Invalid storage engine '{store}' specified. Must be one of:".format(store=bad_store)
        for store in store_map:
            print "  " + store
        sys.exit(1)

    from_store = create_store(from_store)
    to_store = create_store(to_store)

    class MigratingSource(object):
        def __init__(self, id, config):
            self.source_id = id
            self.config = config
            self.kind = self.config['kind']

    sources = from_store.get_sources()
    for source_id, source_data in sources.iteritems():
        to_store.store_source(MigratingSource(source_id, source_data))

    to_store.store_events(list(from_store.events(count=sys.maxint)))

@command()
def publish(app, source_name, *args):
    """publish (name) (key:\"value\") ...: Manually adds an event to a source of kind "publish"."""
    source_id = 'publish:'+source_name
    source = disambiguate(source_id, app.sources, 'source')
    if not source:
        print 'Invalid source specified.'
        sys.exit(1)
    elif source.kind != 'publish':
        print "Invalid source of kind '{kind}' specified.".format(kind=source.kind)
        sys.exit(1)

    data = {}
    for field in args:
        key, value = field.split(':', 1)
        value = value.strip('"\'')
        data[key] = value
    source.publish(**data)
    update(app, source_id)

@command()
def help(app, cmd=None):
    """help (command): I think you know what this does already."""
    if cmd:
        cmd = disambiguate(cmd, _cmds, 'command')
        print cmd.__doc__.strip() if cmd.__doc__ else 'No help available for \'{cmd}\''.format(cmd=cmd.func_name)
    else:
        print 'Help with what?'
        for c in sorted(_cmds.keys()):
            print '   ' + c


def main():
    app = Been()
    if len(sys.argv) < 2:
        cmd = 'help'
    else:
        cmd = sys.argv[1]
    run_command(cmd, app, sys.argv[2:])


if __name__=='__main__':
    main()
