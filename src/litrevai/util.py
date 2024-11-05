import re
import bibtexparser
import pandas as pd
from time import time


def strip_references(text):
    match = re.split('REFERENCES', text, flags=re.MULTILINE)
    text = ''.join(match[:-1])
    return text


def extract_year(date):
    if type(date) is not str:
        return None
    match = re.search(r'[0-9]{4}', date)
    if match:
        return match.group(0)
    else:
        return None

def resolve_items(keys_or_items):
    if keys_or_items is None:
        keys = None
    elif isinstance(keys_or_items, pd.DataFrame):
        keys = keys_or_items.index.tolist()
    elif isinstance(keys_or_items, list):
        keys = keys_or_items
    elif isinstance(keys_or_items, str):
        keys = list(keys_or_items)
    else:
        raise TypeError('Keys must be either of type DataFrame, list or str.')

    return keys


def to_df(objects):

    records = []

    for o in objects:
        columns = o.__table__.columns
        columns = [column.name for column in columns]
        record = {column: getattr(o, column) for column in columns}
        records.append(record)

    df = pd.DataFrame.from_records(records)
    return df


def parse_bibtex(path_to_bibtex):

    with open(path_to_bibtex, 'r') as f:
        s = f.read()

    bib = bibtexparser.parse_string(s)

    entries = [dict(entry.items()) for entry in bib.entries]

    return entries


def get_authors_from_author_field(author_field):
    pass





def timer_func(func):
    # This function shows the execution time of
    # the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f'Function {func.__name__!r} executed in {(t2 - t1):.4f}s')
        return result

    return wrap_func
