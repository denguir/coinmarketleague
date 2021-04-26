from datetime import datetime


def to_series(d: dict):
    '''Transform dict into graphics format'''
    return {'labels': [key for key in d.keys()],
            'data': [value for value in d.values()]}


def to_time_series(d: dict):
    '''Transform dict into graphics with time axis format'''
    return {'labels': [day.strftime('%d %b') for day in d.keys()],
            'data': [value for value in d.values()]}
