#!/usr/bin/env python
import sys
import json
from core import Been, source_registry
from source import *

_cmds = {}
def command(f):
    _cmds[f.func_name] = f
    return f

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

@command
def update(app):
    """update: Fetches events from all sources."""
    app.update()

@command
def add(app, kind, *args):
    """add <kind> (parameters): Registers a source of the specified <kind>."""
    source_cls = source_registry.get(kind)
    if kind:
        app.add(source_cls.configure(*args))

@command
def log(app):
    """log: Displays summaries for the 100 newest events."""
    for event in app.store.events():
        print event['summary'].encode('utf-8')

@command
def list(app):
    """list: Displays the IDs of all registered sources."""
    for source_id in app.sources.iterkeys():
        print '{name}'.format(name = source_id)

@command
def empty(app):
    """empty: Clears the event store of all events."""
    app.store.empty()

@command
def reprocess(app):
    """reprocess: Reprocesses events using their stored data."""
    app.reprocess()

@command
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

@command
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
    app.init()
    cmd = sys.argv[1]
    run_command(cmd, app, sys.argv[2:])

if __name__=='__main__':
    main()
