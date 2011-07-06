class Store(object):
    def __init__(self, config=None):
        self.config = config or {}

    def collapsed_events(self, *args, **kwargs):
        groups = {}
        sources = self.get_sources()
        events = list(self.events(*args, **kwargs))
        for index, event in enumerate(events):
            source = event['source']
            collapse = sources[source].get('collapse', False)
            if collapse == True: collapse = {}

            # Group if the source or the event has a "collapse" property set.
            if collapse != False or event.get('collapse'):
                def group_event():
                    if source not in groups:
                        groups[source] = {
                            "source": source,
                            "kind": event["kind"],
                            "timestamp": event["timestamp"],
                            "index": index,
                            "children": []
                        }
                    group = groups[source]

                    # Group if the event occured within "interval" (default 2 hours) of
                    # the last of the same source.
                    latest = group['timestamp'] if group["children"] else event['timestamp']
                    interval = collapse.get('interval', 2*60*60)
                    # Compare latest - current, since events are ordered descending by timestamp.
                    if group['timestamp'] - event['timestamp'] <= interval:
                        event["collapsed"] = True
                        group["children"].append(event)
                    else:
                        # If a longer interval occurred, empty the group and add it at the position of its last event.
                        events[group["index"]] = group
                        del group["index"]
                        del groups[source]
                        # Add this event to a new group by processing it again (with the cleared group).
                        group_event()
                group_event()

        return filter(lambda e:not e.get("collapsed"), events)
