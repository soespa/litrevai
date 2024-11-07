from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from tqdm.auto import tqdm
from .acm import load_binder
from .pdf2text import pdf2text
from .prompt import Prompt
from .schema import *
from .util import timer_func
from .zotero_connector import ZoteroConnector
from .util import extract_year


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
                            Author.firstName == first_name,
                            Author.lastName == last_name
                        ).first()

                        if not author:
                            author = Author(
                                firstName=first_name,
                                lastName=last_name
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
        author = session.query(Author).where(Author.firstName == first_name, Author.lastName == last_name).first()

        if not author:
            author = Author(
                firstName=first_name,
                lastName=last_name
            )
            session.add(author)
            session.commit()

        # session.expunge(author)
        return author

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

    def import_zotero(
            self,
            zotero_path: str,
            filter_type_names=None,
            filter_libraries=None,
            like=None,
            prog_callback=None,
            debug=False
    ):
        """

        :param zotero:
        :param filter_type_names: List of entry types to be included. Allowed options [conferencePaper, journalArticle, book, bookSection]
        :param filter_libraries: List of groups to be included. If None, include all. For personal library use "Personal".
        :return:
        """

        zotero = ZoteroConnector(zotero_path=zotero_path)

        with self.Session(expire_on_commit=False) as session:

            items = zotero.items

            authors = zotero.authors
            collections = zotero.collections
            libraries = zotero.libraries

            filter_libraries = libraries[libraries['name'].isin(filter_libraries)].index.to_list()

            if filter_libraries:
                items = items[items.libraryID.isin(filter_libraries)]
                collections = collections[collections.libraryID.isin(filter_libraries)]
                libraries = libraries[libraries.index.isin(filter_libraries)]

            if filter_type_names:
                items = items[items.typeName.isin(filter_type_names)]

            for library_id, row in libraries.iterrows():
                library = session.get(Library, library_id)

                if not library:
                    library = Library(id=library_id)
                    library.name = row['name']
                    session.add(library)

            for collection_id, row in collections.iterrows():

                collection = session.get(Collection, collection_id)

                if not collection:
                    collection = Collection(id=collection_id)
                    collection.name = row['collectionName']
                    collection.library_id = row['libraryID']
                    parent_id = row['parentCollectionID']
                    collection.parent_id = parent_id
                    session.add(collection)

            for author_id, row in authors.iterrows():

                author = session.get(Author, author_id)

                if not author:
                    author = Author(id=author_id)
                    author.firstName = row.firstName
                    author.lastName = row.lastName
                    session.add(author)

            session.commit()

            n = len(items)

            i = 0

            for key, row in tqdm(items.iterrows(), total=n, desc='Syncing Zotero'):

                if prog_callback:
                    prog_callback(i, n)
                i += 1

                if session.get(BibliographyItem, key):
                    if debug:
                        print(f'Item with key {key} already in database')
                    continue

                path = row['path']

                try:

                    ft_cache = os.path.join(
                        os.path.dirname(path),
                        '.zotero-ft-cache'
                    )

                    if os.path.exists(ft_cache):
                        with open(ft_cache, 'r') as f:
                            text = f.read()
                    else:
                        text = pdf2text(path)
                except Exception as e:
                    print(e)
                    continue

                typeName = row['typeName']

                if typeName in zotero_to_entrytype:
                    entry_type = zotero_to_entrytype[typeName]
                else:
                    entry_type = EntryTypes.MISC

                bib_item = BibliographyItem(key=key)
                bib_item.zotero_key = key
                bib_item.title = row['title']
                bib_item.typeName = entry_type.value
                bib_item.text = text
                bib_item.path = row['path']
                bib_item.year = row['year']
                bib_item.DOI = row['DOI']
                bib_item.ISBN = row['ISBN']
                bib_item.library_id = row['libraryID']

                session.add(bib_item)

                creator_ids = row['creatorIDs']

                if isinstance(creator_ids, list):
                    for creator_id in creator_ids:
                        author = session.get(Author, creator_id)

                        if author not in bib_item.authors:
                            bib_item.authors.append(author)

                collection_ids = row['collectionIDs']

                if isinstance(collection_ids, list):
                    for collection_id in collection_ids:
                        collection = session.get(Collection, collection_id)

                        if bib_item not in collection.items:
                            collection.items.append(bib_item)

                session.commit()

    def load_binder(
            self,
            base_path: str,
            project_id: int | None = None
    ):
        """
        Import individual items from an ACM Binder.

        """

        try:
            articles, df = load_binder(base_path)

            for index, row in df.iterrows():
                if 'doi' in row.index:
                    doi = row['doi']
                else:
                    doi = row['ID']

                if doi in articles.keys():
                    print(doi)
                    text = articles[doi]
                    item = self.add_item_by_bibtex(key=doi, bibtex=row.to_dict(), text=text)
                    if project_id:
                        self.add_item_to_project(item.key, project_id)
        except Exception as e:
            print(e)
