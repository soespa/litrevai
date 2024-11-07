import re
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from tqdm.auto import tqdm


def pdf2text(path):
    """
    Extracts raw text from pdf
    :param path:
    :return:
    """
    lines = []
    for i, page_layout in enumerate(extract_pages(path)):
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                lines.append(element.get_text())

    text = '\n'.join(lines)

    def cleanup_text(text):
        text = re.sub(r'[^a-zA-ZÄÖÜß0-9\.:;,!?()\[\]@"\' \n\-]', '', text)
        return text

    text = cleanup_text(text)
    return text


