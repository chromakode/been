import calendar
import pickle
import time

def dates_to_epoch(d):
    """Recursively converts all dict values that are struct_times to Unix timestamps."""
    for key, value in d.iteritems():
        if hasattr(value, 'iteritems'):
            d[key] = dates_to_epoch(value)
        elif type(value) is time.struct_time:
            d[key] = int(calendar.timegm(value))
    return d

def unpickle_dict(dict_):
    """Accepts a dict of pickled items and returns a dict of unpickled items."""
    return dict((k, pickle.loads(v)) for k, v in dict_.iteritems())
