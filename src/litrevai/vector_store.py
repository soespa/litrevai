from typing import Tuple

import lancedb
import pandas as pd
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector, List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .database import *
from .util import strip_references, _resolve_item_keys
import torch


if torch.backends.mps.is_available():
    device = 'mps'
elif torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'

model = get_registry().get("sentence-transformers").create(name="BAAI/bge-large-en-v1.5", device=device)





class Document(LanceModel):
    text: str = model.SourceField()
    vector: Vector(model.ndims()) = model.VectorField()
    key: str
    chunk: int


class VectorStore:

    """
    Manages access to the vector store and provides methods for RAG and similarity search.
    """

    def __init__(self, uri="./.lancedb", llm=None, chunk_size=1024, chunk_overlap=256):

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vs = lancedb.connect(uri)

        self.documents = self.vs.create_table("documents", schema=Document.to_arrow_schema(), exist_ok=True)

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len)

        self.llm = llm

    def delete_all(self):
        self.documents = self.vs.create_table("documents", schema=Document.to_arrow_schema(), mode='overwrite')


    def get_keys(self):
        """
        Returns all unique keys from the database.

        :return: List of unique keys
        """
        docs = self.documents.to_pandas()

        return list(docs['key'].unique())

    def add_text(self, key, text, debug=False):

        if len(self.documents.search().where(f'key = "{key}"').to_pandas()) > 0:
            if debug:
                print(f'Document with key {key} already in Vector store')
            return False

        text = strip_references(text)

        texts = self.splitter.split_text(text)

        n = len(texts)

        data = pd.DataFrame({
            'text': texts,
            'chunk': range(n)
        }).assign(key=key)

        self.documents.add(data=data)

        return True

    def get_context(self, search_phrase, keys: None | List[str] = None, n=10, sort_by_position=True) -> pd.DataFrame:
        """
        Retrieves the context that fits the query using similarity search.

        :param search_phrase:
        :param keys: If None, search within all items. If a list of strings is passed, only items with the keys are considered.
        :param n: Number of chunks to return
        :param sort_by_position: If True, sort chunks by they order they appear in the text
        :return:
        """

        # TODO: Add re-ranker (https://huggingface.co/BAAI/bge-reranker-v2-m3)

        if keys is not None:

            if type(keys) == str:
                filter_keys = "key = '{}'".format(keys)

            elif type(keys) == list:
                key_string = ', '.join([f"'{key}'" for key in keys])
                filter_keys = f"key IN ({key_string})"
            elif isinstance(keys, pd.DataFrame):
                key_string = ', '.join([f"'{key}'" for key in keys.index])
                filter_keys = f"key IN ({key_string})"

            context = self.documents.search(search_phrase).where(filter_keys, prefilter=True).limit(n).to_pandas()
        else:
            context = self.documents.search(search_phrase).limit(n).to_pandas()

        if sort_by_position:
            context = context.sort_values('chunk')

        return context

    def rag(
            self,
            prompt,
            keys: None | str | List[str] = None,
            max_new_tokens: int = 2048,
            temperature: float = 0.6,
            top_p: float = 0.9,
            sort_by_position=True,
            n=20,
            additional_context: dict | None = None
    ) -> Tuple[str, str]:

        """
        Performs Retrieval Augmented Generation using the given prompt on one or more items.

        :param prompt: Prompt which contains the question
        :param keys:
        :param max_new_tokens:
        :param temperature:
        :param top_p:
        :param sort_by_position: If true, sorts retrieved context by its position in the text rather than by its similarity.
        :param n: Number of context chunks to be retrieved. High values may lead to exceeded context size.
        :param additional_context: Dict containing addition metadata that is added to the context.
        :return: Tuple with the answer and the retrieved context.
        """

        context = self.get_context(search_phrase=prompt.question, keys=keys, n=n, sort_by_position=sort_by_position)

        formatted_context = "\n\n".join(context['text'])

        if additional_context is not None:
            lines = []
            for key, value in additional_context.items():
                lines.append(f'{key}: {value}')
            formatted_context = '\n'.join(lines) + '\n' + formatted_context

        messages = prompt.messages(formatted_context)

        answer = self.llm.generate_text(
            messages,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_p=top_p
        )

        return answer, formatted_context
