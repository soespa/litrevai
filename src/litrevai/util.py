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

def _resolve_item_keys(keys_or_items):
    if keys_or_items is None:
        return None
    elif isinstance(keys_or_items, pd.DataFrame):
        return keys_or_items.index.tolist()
    elif isinstance(keys_or_items, list):
        return keys_or_items
    elif isinstance(keys_or_items, str):
        return list(keys_or_items)
    else:
        raise TypeError('Keys must be either of type DataFrame, list or str.')



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


def to_bibtex(items, filename: str = 'bibliography_export.bib'):

    # Initialize a list to store BibTeX entries
    bibtex_entries = []

    # Loop through each item and convert to BibTeX entry format
    for item in items:
        # Prepare authors if available
        authors = " and ".join([f"{author.first_name} {author.last_name}" for author in item.authors])

        # Construct a BibTeX entry dictionary
        entry = {
            'ID': item.key,
            'ENTRYTYPE': item.typeName or 'article',  # Default to 'article' if type is missing
            'title': item.title,
            'author': authors,
            'year': str(item.year) if item.year else '',
            'journal': item.journal,
            'publisher': item.publisher,
            'doi': item.DOI,
            'isbn': item.ISBN,
            'series': item.series,
            'keywords': item.keywords,
            'note': item.note,
            'abstract': item.abstract,
            'file': item.path,
            'date': item.date,
        }



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
