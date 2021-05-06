from datetime import datetime
import pandas as pd

def to_series(df: pd.DataFrame):
    '''Transform dict into graphics format'''
    return {'labels': [key for key in d.keys()],
            'data': [value for value in d.values()]}


def to_time_series(df: pd.DataFrame):
    '''Transform dict into graphics with time axis format'''
    return {'labels': df['day'].apply(lambda x: x.strftime('%d %b')),
            'data': [value for value in d.values()]}
