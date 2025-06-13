from typing import List
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker
from tqdm.auto import tqdm
from litrevai.acm import import_binder
from litrevai.pdf2text import pdf2text
from litrevai.prompt import Prompt
from .models import *
from litrevai.util import timer_func
from litrevai.zotero_connector import ZoteroConnector
from litrevai.util import extract_year
import logging
logger = logging.getLogger(__name__)

class Database:

    def __init__(self, url='sqlite:///library.db'):
        self.url = url
        self.engine = create_engine(url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_or_create_project(self, name):
        with self.Session(expire_on_commit=False) as session:
            project = session.query(ProjectModel).where(ProjectModel.name == name).first()

            if not project:
                project = ProjectModel(name=name)
                session.add(project)
                session.commit()

        return project

    def delete_query(self, query_id):
        with self.Session() as session:
            query = session.get(QueryModel, query_id)
            if query:
                session.delete(query)
                session.commit()
                return True
            return False

    def delete_project(self, project_id):
        with self.Session() as session:
            project = session.get(ProjectModel, project_id)
            if project:
                session.delete(project)
                session.commit()
                return True
            return False

    def delete_all_responses(self, project_id: int = None):
        with self.Session() as session:

            if project_id is None:
                responses = session.query(Response).all()
                for response in responses:
                    session.delete(response)
            else:
                project = session.get(ProjectModel, project_id)
                queries = project.queries
                for query in queries:
                    for response in query.responses:
                        session.delete(response)

            session.commit()

    def get_responses_for_project(self, project_id):
        with self.Session() as session:
            project = session.get(ProjectModel, project_id)
            queries = project.queries

            # items = project.items

            data = []

            for query in queries:
                responses = query.responses

                d = {}
                for response in responses:
                    d[response.item_key] = response.value

                data.append(pd.Series(d, name=query.name))

            df = pd.concat(data, axis=1)

            df.index.name = 'key'

            return df

    def get_responses_for_query(self, query_id):
        with self.Session() as session:
            query = session.get(QueryModel, query_id)
            responses = query.responses

            d = {}
            for response in responses:
                d[response.item_key] = response.value

        s = pd.Series(d, name=query.name)

        return s

    def clear_responses(self, session: Session, query_id: int):
        query = session.get(QueryModel, query_id)

        responses = query.responses
        for response in responses:
            session.delete(response)

    def get_project(self, project_id):
        with self.Session() as session:
            project = session.get(ProjectModel, project_id)
        return project

    def add_item_by_bibtex(self, key: str, bibtex: dict, text: str = None):
        """
        Add a parsed BibTeX entry to the bibliography_items table.

        :param session: SQLAlchemy Session
        :param text: The plain full text.
        :param bibtex: Dictionary containing the BibTeX fields.
        """

        with self.Session() as session:

            item = session.get(BibliographyItem, key)

            if not item:

                year = None
                if 'date' in bibtex:
                    year = extract_year(bibtex.get('date'))

                # Create a new BibliographyItem instance with the parsed data
                item = BibliographyItem(
                    key=bibtex.get('ID'),
                    typeName=bibtex.get('ENTRYTYPE'),
                    DOI=bibtex.get('doi'),
                    ISBN=bibtex.get('isbn'),
                    title=bibtex.get('title'),
                    year=year,
                    abstract=bibtex.get('abstract'),
                    series=bibtex.get('series'),
                    journal=bibtex.get('journaltitle'),
                    publisher=bibtex.get('publisher'),
                    keywords=bibtex.get('keywords'),
                    text=text
                )

                session.add(item)
                session.commit()

                author_string = bibtex.get('author')
                authors = author_string.split(' and ')

                for s in authors:
                    try:
                        last_name, first_name = s.split(', ')

                        author = session.query(Author).where(
                            Author.first_name == first_name,
                            Author.last_name == last_name
                        ).first()

                        if not author:
                            author = Author(
                                first_name=first_name,
                                last_name=last_name
                            )
                            session.add(author)

                        print(author)

                        author.items.append(item)

                        session.commit()
                    except Exception as e:
                        print(e)
                        print(f"Parsing name {s} failed.")

                session.commit()

                print(f"Added BibTeX entry with key {item.key}")

        return item

    def add_item_to_project(self, item_key: str, project_id: str):
        with self.Session() as session:
            project = session.get(ProjectModel, project_id)
            item = session.get(BibliographyItem, item_key)

            if item not in project.items:
                project.items.append(item)
                session.commit()
                return True
        return False

    def remove_items_from_project(self, session, item_keys: List[str], project_id: str):
        project = session.get(ProjectModel, project_id)
        items_to_remove = session.query(BibliographyItem).filter(BibliographyItem.key.in_(item_keys)).all()

        for item in tqdm(items_to_remove, total=len(items_to_remove), desc='Deleting items from project'):
            if item in project.items:
                project.items.remove(item)

    def remove_item_from_project(self, item_key: str, project_id: str):
        with self.Session() as session:
            project = session.get(ProjectModel, project_id)
            item = session.get(BibliographyItem, item_key)

            if item in project.items:
                project.items.remove(item)
                session.commit()
                return True
        return False

    def add_response(self, query_id, item_key, text):

        with self.Session() as session:
            response = Response(
                query_id=query_id,
                item_key=item_key,
                text=text
            )

            session.add(response)
            session.commit()

    def add_items_to_project(self, session, item_keys: List[str], project_id: str):

        project = session.get(ProjectModel, project_id)
        items_to_add = session.query(BibliographyItem).filter(BibliographyItem.key.in_(item_keys)).all()

        for item in tqdm(items_to_add, total=len(items_to_add), desc='Adding items to project'):
            if item not in project.items:
                project.items.append(item)

    def create_query(self, project_id: int, name: str, prompt: Prompt):
        with self.Session(expire_on_commit=False) as session:
            query = QueryModel(
                project_id=project_id,
                name=name,
                question=prompt.question,
                type=prompt.name,
                params=json.dumps(prompt.params)
            )
            session.add(query)
            session.commit()

        return query

    def get_query_by_id(self, session: Session, query_id):
        query = session.get(QueryModel, query_id)
        return query

    def get_query_by_name(self, session: Session, name: str):
        query = session.query(QueryModel).where(QueryModel.name == name).first()
        return query

    def get_or_create_query(self, project_id: int, name: str, prompt: Prompt):

        with self.Session(expire_on_commit=False) as session:
            query = session.query(QueryModel).where(
                QueryModel.project_id == project_id,
                QueryModel.name == name,
                QueryModel.question == prompt.question,
                QueryModel.type == prompt.name
            ).first()

            if not query:
                query = QueryModel(
                    project_id=project_id,
                    name=name,
                    question=prompt.question,
                    type=prompt.name,
                    params=json.dumps(prompt.params)
                )
                session.add(query)
                session.commit()

        return query

    def get_or_create_author_by_name(self, first_name, last_name):
        session = self.session
        author = session.query(Author).where(Author.first_name == first_name, Author.last_name == last_name).first()

        if not author:
            author = Author(
                first_name=first_name,
                last_name=last_name
            )
            session.add(author)
            session.commit()

        # session.expunge(author)
        return author

    def get_items_by_author(self, session, author_id):
        author = session.get(Author, author_id)
        items = session.query(BibliographyItem).where(BibliographyItem.authors.contains(author)).all()
        return items

    def search_author(self, session, search_name):
        authors = session.query(Author).filter(
            or_(
                Author.first_name.ilike(f"%{search_name}%"),
                Author.last_name.ilike(f"%{search_name}%"),
                Author.full_name.ilike(f"%{search_name}%")
            )
        ).all()

        return authors

    def add_response(self, query, item, text):
        response = Response(query=query, item=item)
        response.text = text

        self.session.add(response)
        self.session.commit()

    def get_collection(self, collection_id):
        with self.Session() as session:
            collection = session.get(Collection, collection_id)
        return collection

    def get_library(self, library_id):
        with self.Session() as session:
            query = session.get(Library, library_id)
        return query

    @property
    def items(self):
        with self.Session() as session:
            items = session.query(BibliographyItem).all()

        df = BibliographyItem.to_df(items)
        return df

    @property
    def collections(self):
        session = Session(self.engine)
        df = pd.read_sql(session.query(Collection).statement, session.bind)
        session.close()
        df = df.set_index('id')
        return df

    @property
    def queries(self):
        session = Session(self.engine)
        df = pd.read_sql(session.query(QueryModel).statement, session.bind)
        session.close()

        df = df.set_index('id')

        return df

    @property
    def responses(self):
        session = Session(self.engine)
        df = pd.read_sql(session.query(Response).statement, session.bind)
        session.close()

        df = df.set_index('id')

        return df

    @property
    def projects(self):
        session = Session(self.engine)
        df = pd.read_sql(session.query(ProjectModel).statement, session.bind)
        session.close()

        df = df.set_index('id')

        return df

    def import_zotero(self, zotero: ZoteroConnector):

        with self.Session(expire_on_commit=False) as session:
            # Libraries
            for lib_id, row in zotero.libraries.iterrows():
                session.merge(Library(id=lib_id, name=row['name']))
            session.commit()

            # Collections
            for collection_id, row in zotero.collections.iterrows():
                session.merge(Collection(
                    id=collection_id,
                    name=row['collectionName'],
                    library_id=row['libraryID'],
                    parent_id=row['parentCollectionID'],
                ))
            session.commit()

            # Authors
            for author_id, row in zotero.authors.iterrows():
                session.merge(Author(
                    id=author_id,
                    first_name=row['firstName'],
                    last_name=row['lastName']
                ))
            session.commit()

            # Bibliography items
            for key, row in zotero.items.iterrows():

                if session.get(BibliographyItem, key):
                    logger.info(f"Item {key} already exists")
                    continue

                try:
                    ft_cache = os.path.join(os.path.dirname(row['path']), '.zotero-ft-cache')
                    if os.path.exists(ft_cache):
                        with open(ft_cache, 'r') as f:
                            text = f.read()
                    else:
                        text = pdf2text(row['path'])
                except Exception as e:
                    print(f"Error reading file {row['path']}: {e}")
                    continue

                entry_type = zotero_to_entrytype.get(row['typeName'], EntryTypes.MISC)

                item = BibliographyItem(
                    key=key,
                    zotero_key=key,
                    title=row['title'],
                    typeName=entry_type.value,
                    text=text,
                    path=row['path'],
                    year=row['year'],
                    DOI=row.get('DOI'),
                    ISBN=row.get('ISBN'),
                    library_id=row['libraryID'],
                    synced=False
                )
                session.add(item)
                session.commit()

            # Link item -> creators
            for i, row in tqdm(zotero.item_creators.iterrows(), total=len(zotero.item_creators),
                               desc="Linking authors"):
                item = session.get(BibliographyItem, row['key'])
                author = session.get(Author, row['creatorID'])
                if author not in item.authors:
                    item.authors.append(author)
                session.commit()

            # Link item -> collections
            for i, row in tqdm(zotero.item_collections.iterrows(), total=len(zotero.item_collections),
                               desc="Linking collections"):
                item = session.get(BibliographyItem, row['key'])
                collection = session.get(Collection, row['collectionID'])
                if item not in collection.items:
                    collection.items.append(item)
                session.commit()


