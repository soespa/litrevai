import json
from typing import List, TYPE_CHECKING

import pandas as pd

from .util import _resolve_item_keys
from .prompt import Prompt
from .query import Query
from .model.models import BibliographyItem, ProjectModel, Collection, Library, QueryModel

if TYPE_CHECKING:
    from .literature_review import LiteratureReview
    from .model.database import Database


class Project:

    """
    A project contains a collection of BibliographyItems and a set of queries.
    When the project is executed, it runs all queries over all items in the project.
    """

    db: 'Database'
    _project_id: int

    def __init__(self, lr: 'LiteratureReview', project_id: int):
        self.lr = lr
        self.db = lr.db
        self._project_id = project_id

        self.Session = self.db.Session

    @property
    def project_id(self):
        return self._project_id

    @property
    def project_model(self):
        with self.db.Session() as session:
            project_model = session.get(ProjectModel, self.project_id)
        return project_model

    @property
    def name(self):
        project_model = self.project_model
        return project_model.name

    @property
    def queries(self):
        with self.Session() as session:
            project = session.get(ProjectModel, self.project_id)
            queries = project.queries

        return {
            query_model.name: Query(self.lr, query_model.id)
            for query_model in queries
        }


    def create_query(self, name: str, prompt: Prompt, exists_ok=True) -> Query:
        """
        Create a query and add it to the project.
        Raises an error if a query with the given name already exists.

        :param name: Unique name for the prompt.
        :param prompt: A prompt that inherits from Prompt.
        :return: Returns the created prompt
        """
        with self.Session(expire_on_commit=False) as session:
            query_model = session.query(QueryModel).where(
                QueryModel.project_id == self.project_id,
                QueryModel.name == name,
            ).first()

            if not query_model:
                query_model = QueryModel(
                    project_id=self.project_id,
                    name=name,
                    question=prompt.question,
                    type=prompt.name,
                    params=json.dumps(prompt.params)
                )
                session.add(query_model)
                session.commit()
            else:
                # TODO: Add check if prompt differs to give the user a warning
                if not exists_ok:
                    raise Exception(f'Query with name {name} already exists.')

        query = Query(self.lr, query_id=query_model.id)
        return query

    def delete_query(self, name: str) -> None:

        with self.Session() as session:
            query_model = session.query(QueryModel).where(
                QueryModel.project_id == self.project_id,
                QueryModel.name == name,
            ).first()

            if not query_model:
                raise Exception('There is no query with name {name}.')
            else:
                session.delete(query_model)


    @property
    def responses(self) -> pd.DataFrame:
        return self.db.get_responses_for_project(self.project_id)


    @property
    def items(self) -> pd.DataFrame:
        with self.Session() as session:
            items = session.get(ProjectModel, self.project_id).items

        df = BibliographyItem.to_df(items)
        return df


    def rag(self, prompt, items = None):
        if items is None:
            items = self.items

        keys = _resolve_item_keys(items)

        self.lr.rag(prompt=prompt, keys=keys)

    def search(self, search_phrase: str, n: int = 10) -> pd.DataFrame:
        """
        Performs a full-text similarity search based on the provided search phrase for all items in the project.

        :param search_phrase: The phrase to search for within the items
        :param n: The number of items to return
        :return: A DataFrame containing the matching text passages and their respective sources.
        """
        items = self.items
        df = self.lr.search(
            search_phrase=search_phrase,
            n=n,
            items=items
        )
        return df

    @property
    def import_bibtex(self, path_to_bibtex: str):
        self.lr.import_bibtex(path_to_bibtex, self.project_id)


    def test(self):
        self.lr.test_project(self.project_id)

    def delete_project(self):
        self.db.delete_project(self.project_id)

    def sample(self) -> str:
        """
        Returns a random item from the project. Useful for testing prompts.
        :return:
        """

        items = self.items

        if len(items) > 0:
            key = items.sample(1).iloc[0].name
            item = self.lr.get_item(key)
            return item
        else:
            raise Exception('The projects contains no items to sample from.')

    def add_items(self, items) -> None:
        """
        Adds one or more items from the database to the project.

        :param items: Items to add to the project.
        """

        keys = _resolve_item_keys(items)

        with self.Session() as session:
            self.db.add_items_to_project(session, keys, self.project_id)
            session.commit()

    def remove_items(self, items):
        """
        Removes one or more items from the project.
        Does not delete the items from the database.

        :param items: Items to remove from the project.
        """

        keys = _resolve_item_keys(items)

        with self.Session() as session:
            self.db.remove_items_from_project(session, keys, self.project_id)
            session.commit()


    def run(self, include_keys: List[str] | None = None):
        self.lr.run_project(self.project_id, include_keys=include_keys)


    def add_items_from_collection(self, collection_name):

        with self.Session() as session:
            collection = session.query(Collection).where(Collection.name == collection_name).first()
            if collection:
                project = session.get(ProjectModel, self.project_id)
                for item in collection.items:
                    project.items.append(item)
            session.commit()



    def to_excel(self, filepath, query_names=None, items=None):
        responses = self.responses
        items = self.items[['DOI', 'ISBN', 'title', 'year', 'authors_list']]
        df = responses.join(items)

        keys = _resolve_item_keys(items)

        df = df.loc[keys]
        df.to_excel(filepath)

    def __repr__(self):
        return f'Project<name={self.name}>'


