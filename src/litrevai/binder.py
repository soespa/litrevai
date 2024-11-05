import os
import bibtexparser
import pandas as pd
import os.path
import re
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTFigure, LTChar, LTTextBoxHorizontal



def load_binder(base_path: str):
    d = {}
    article = []
    doi = None
    pdf_path = os.path.join(base_path, 'proceedings.pdf')

    for i, page_layout in enumerate(extract_pages(pdf_path)):

        is_article = True
        print(f'=== Page {i} ===')

        # Check if article page or preface
        for elem in page_layout:
            if isinstance(elem, LTTextBoxHorizontal):
                s = elem.get_text()
                match = re.search(r'The ACM Digital Library is published by the Association for Computing Machinery', s)
                if match:
                    is_article = False
                    break

        # If article add to
        if is_article:
            lines = []
            for elem in page_layout:
                if isinstance(elem, LTTextContainer):
                    lines.append(elem.get_text())
            article.append('\n'.join(lines))
        # If not check
        else:
            if len(article) > 0:
                text = '\n'.join(article)
                text = re.sub(r'ﬁ', 'fi', text)
                d[doi] = text
                article = []
            for elem in page_layout:
                if isinstance(elem, LTTextBoxHorizontal):
                    s = elem.get_text()
                    match = re.search(r'doi > ([0-9./]+)', s)
                    if match:
                        doi = match.group(1)
                        print(doi)

    if len(article) > 0:
        text = '\n'.join(article)
        text = re.sub(r'ﬁ', 'fi', text)
        d[doi] = text
        article = []

    bib_file = os.path.join(base_path, 'acm.bib')

    with open(bib_file, 'r') as f:
        s = f.read()

    bib = bibtexparser.parse_string(s)

    records = [dict(entry.items()) for entry in bib.entries]

    df = pd.DataFrame.from_records(records)

    return d, df

