from random import randint
from typing import List, Mapping
import pandas as pd
from sqlalchemy.orm import Session
from tqdm.auto import tqdm
import os
from .llm import BaseLLM
from .pdf2text import pdf2text
from .query import Query
from .schema import ProjectModel, Response, QueryModel, Library, Collection, BibliographyItem
from .topic_modelling import TopicModel
from .util import parse_bibtex
from .project import Project
from .database import Database
from .zotero_connector import ZoteroConnector
from .vector_store import VectorStore


class LiteratureReview:
    """
    Literature Review manages access to projects, the database and the vector store.
    """

    db: Database
    vs: VectorStore
    llm: BaseLLM

    def __init__(self, path='./db', llm=None):

        if not os.path.exists(path):
            os.mkdir(path)

        self.db = Database(f'sqlite:///{path}/bibliography.sqlite')
        self.vs = VectorStore(uri=f'{path}/lancedb', llm=llm)
        self.llm = llm
        self.rag = self.vs.rag

        self.Session = self.db.Session


    def get_item(self, item_key):
        """
        Returns the BibliographyItem for the given key.
        :param item_key:
        :return:
        """
        with self.Session() as session:
            item = session.get(BibliographyItem, item_key)
        return item


    @property
    def collections(self):
        with self.Session() as session:
            collections = session.query(Collection).all()

        d = {collection.id: collection.name for collection in collections}
        return d


    def get_collection(self, collection_id):
        with self.Session() as session:
            collection = session.get(Collection, collection_id)
            items = collection.items

        df = BibliographyItem.to_df(items)
        return df

    def get_library(self, library_id):
        with self.Session() as session:
            library = session.get(Library, library_id)
            items = library.items

        df = BibliographyItem.to_df(items)
        return df

    @property
    def items(self) -> pd.DataFrame:
        """
        Returns all the items in the database as a DataFrame.

        :return: DataFrame containing all items in the database.
        """
        return self.db.items

    @property
    def projects(self) -> Mapping[str, Project]:
        """
        Provides access to projects.

        :return: Returns a dict containing all projects which can be accessed by their names.
        """
        with self.Session() as session:
            projects = session.query(ProjectModel).all()
        return {
            project.name: Project(self, project.id)
            for project in projects
        }


    # def get_or_create_project(self, name):
    #     project_model = self.db.get_or_create_project(name)
    #     project = Project(self, project_model.id)
    #     return project

    def create_project(self, name: str) -> Project:
        """
        Creates a Project with the given (unique) name.

        :param name: Unique name to identify the project.
        :return: Project that has been created.
        """
        with self.Session(expire_on_commit=False) as session:
            project_model = session.query(ProjectModel).where(
                ProjectModel.name == name
            ).first()

            if project_model:
                raise Exception(f'Project with name {name} already exits.')

            else:
                project_model = ProjectModel(
                    name=name
                )
                session.add(project_model)
                session.commit()

        project = Project(self, project_model.id)
        return project

    def delete_project(self, name: str):
        """
        Deletes the project with the given name. Raises an error if there is no project with the given name.

        :param name: Name of the project that should be deleted.
        :return:
        """
        with self.Session(expire_on_commit=False) as session:
            project_model = session.query(ProjectModel).where(
                ProjectModel.name == name
            ).first()

            if project_model:
                session.delete(project_model)
                session.commit()
            else:
                raise Exception('Project with name {name} does not exists.')


    def resolve_project(self, project):
        if project is None:
            return None

        if isinstance(project, int):
            project_id = project
        if isinstance(project, Project):
            project_id = project.project_id

        return project_id

    def import_bibtex(self, path_to_bibtex: str, project: int | Project = None):
        """
        Imports BibliographyItems into the database from a Bibtex File. The entries are expected to have a `file` field
        containing the absolute path to the corresponding PDF file.

        :param path_to_bibtex:
        :param project_id: Optional Project ID. Items are automatically added to the project
        :return:
        """

        project_id = self.resolve_project(project)

        entries = parse_bibtex(path_to_bibtex)
        for entry in entries:
            filepath = entry.get('file')
            if filepath is None:
                print(f'No file associated with this entry: {entry}')
                continue

            filepath = os.path.join(os.path.dirname(path_to_bibtex), filepath)

            text = pdf2text(filepath)
            item = self.db.add_item_by_bibtex(entry, text)

            if project_id:
                self.db.add_item_to_project(item.key, project_id)

    @property
    def libraries(self):
        with self.Session() as session:
            libraries = session.query(Library).all()

        d = {library.id: library.name for library in libraries}
        return d

    def update_vector_store(self, redo: bool = False) -> None:
        """
        Looks for items that have not been added to the vector store yet and adds them.

        :param redo: If True, deletes all entries in the vector store before adding all items.
        :return:
        """
        if redo:
            self.vs.delete_all()

        items = self.db.items
        keys_in_vs = self.vs.get_keys()
        items = items.drop(keys_in_vs)
        progress_bar = tqdm(desc='Updating Vector Store', total=len(items))

        for key, row in items.iterrows():
            text = row['text']
            self.vs.add_text(key, text)
            progress_bar.update()

    def import_zotero(
            self,
            zotero_path: str | None = None,
            filter_type_names: List[str] | None = None,
            filter_libraries: List[str] | None = None):
        """
        Connects to a local instance of Zotero and add items that fit to the filter criteria.

        :param zotero_path: Directory containing Zotero Files
        :param filter_type_names: One of
            -
        :param filter_libraries:
        :return:
        """

        zotero = ZoteroConnector(zotero_path=zotero_path)

        self.db.sync_zotero(zotero, filter_type_names, filter_libraries)

        for key, row in self.db.items.iterrows():
            text = row['text']
            self.vs.add_text(key, text)

    def run_query(self, query_id, include_keys=None, save_responses=True, debug=False):
        with self.db.Session() as session:
            query = session.get(QueryModel, query_id)
            project = query.project
            items = project.items

            # Filter for include keys
            if include_keys:
                items = [item for item in items if item.key in include_keys]

            progress_bar = tqdm(desc=f'Retrieving responses for query {query.id}', total=len(items))

            for item in items:

                progress_bar.update()

                # Check if there is already a response for this query
                response = session.query(Response).where(
                    Response.query == query,
                    Response.item == item
                ).first()

                if response:
                    continue

                prompt = query.prompt

                additional_context = {
                    'title': str(item.title)
                }

                answer, context = self.vs.rag(
                    prompt=prompt,
                    keys=item.key,
                    additional_context=additional_context
                )

                if debug:
                    print(answer)

                if save_responses:
                    response = Response(
                        query=query,
                        item=item,
                        text=answer,
                        context=context
                    )

                    session.add(response)
                    session.commit()


    def test_query(self, query_id):
        with self.db.Session() as session:
            query = session.get(QueryModel, query_id)
            project = query.project

            items = project.items
            item = items[randint(0, len(items)-1)]
            prompt = query.prompt

            answer, context = self.vs.rag(
                prompt=prompt,
                keys=item.key,
            )

            response = Response(
                query=query,
                item=item,
                text=answer,
                context=context
            )

            print(response)


    def test_project(self, project_id):
        """
        Tests all queries from the project.

        :param project_id:
        :return:
        """

        with self.db.Session() as session:
            project = session.get(ProjectModel, project_id)

            items = project.items
            queries = project.queries

            item = items[randint(0, len(items)-1)]

            for query in tqdm(queries, desc='Retrieving Responses', total=len(queries)):

                prompt = query.prompt

                answer, context = self.vs.rag(
                    prompt=prompt,
                    keys=item.key,
                )

                response = Response(
                    query=query,
                    item=item,
                    text=answer,
                    context=context
                )

                print(response)




    def run_project(self, project_id, include_keys: List[str] | None = None):
        """
        Runs over all items in a project

        :param include_keys:
        :param project_id:
        :return:
        """

        with self.db.Session() as session:
            project = session.get(ProjectModel, project_id)

            items = project.items
            queries = project.queries

            # Filter for include keys
            if include_keys:
                items = [item for item in items if item.key in include_keys]

            for item in tqdm(items, total=len(items), desc='Retrieving responses for project'):
                for query in queries:

                    response = session.query(Response).where(Response.query==query, Response.item == item).first()

                    if response:
                        continue

                    prompt = query.prompt

                    answer, context = self.vs.rag(
                        prompt=prompt,
                        keys=item.key,
                    )

                    response = Response(
                        query=query,
                        item=item,
                        text=answer,
                        context=context
                    )

                    print(response)

                    session.add(response)
                    session.commit()

    def create_topic_model(self, query_id):

        query = Query(self, query_id)
        topic_model = TopicModel(self.items, query.responses)
        return topic_model


class LibraryController:

    _library_id: int

    def __init__(self, library_id: int, lr: LiteratureReview):
        self._library_id = library_id
        self.lr = lr

    @property
    def library_id(self):
        return self._library_id

    @property
    def collections(self):
        pass


class CollectionController:

    _collection_id: int

    def __init__(self, collection_id: int, lr: LiteratureReview):
        self.lr = lr
        self._collection_id = collection_id


    @property
    def collection_id(self):
        return self._collection_id
