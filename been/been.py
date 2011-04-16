#!/usr/bin/env python
import sys
from core import Been, source_registry
from source import *

_cmds = {}
def command(f):
    _cmds[f.func_name] = f
    return f

def run_command(cmd, app, args):
    _cmds[cmd](app, *args)

@command
def update(app):
    app.update()

@command
def add(app, kind, *args):
    source_cls = source_registry.get(kind)
    if kind:
        app.add(source_cls.configure(*args))

@command
def log(app):
    for event in app.store.events():
        print event['summary'].encode('utf-8')

@command
def list(app):
    for source_id in app.sources.iterkeys():
        print '{name}'.format(name = source_id)

@command
def empty(app):
    app.store.empty()

@command
def reprocess(app):
    app.reprocess()

def main():
    app = Been()
    app.init()
    cmd = sys.argv[1]
    run_command(cmd, app, sys.argv[2:])

if __name__=='__main__':
    main()
