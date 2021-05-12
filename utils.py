from datetime import datetime
import pandas as pd

def to_series(d: dict):
    '''Transform dict into graphics format'''
    return {'labels': [key for key in d.keys()],
            'data': [value for value in d.values()]}

