import json
import os.path
import re
from enum import Enum
from typing import Literal

import pandas as pd
from sqlalchemy import Column, String, Integer, ForeignKey, Table, DateTime, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, relationship, mapped_column, Session
from sqlalchemy.sql import func

from .prompt import prompt_registry


class EntryTypes(Enum):
    ARTICLE = 'article'
    BOOK = 'book'
    BOOKLET = 'booklet'
    CONFERENCE = 'conference'
    INBOOK = 'inbook'
    INCOLLECTION = 'incollection'
    INPROCEEDINGS = 'inproceedings'
    MANUAL = 'manual'
    MASTERSTHESIS = 'mastersthesis'
    MISC = 'misc'
    PHDTHESIS = 'phdthesis'
    PROCEEDINGS = 'proceedings'
    TECHREPORT = 'techreport'
    UNPUBLISHED = 'unpublished'


zotero_to_entrytype = {
    "book": EntryTypes.BOOK,
    "bookSection": EntryTypes.INBOOK,
    "conferencePaper": EntryTypes.INPROCEEDINGS,
    "journalArticle": EntryTypes.ARTICLE,
    "report": EntryTypes.TECHREPORT,
    "thesis": EntryTypes.PHDTHESIS,
}


class Base(DeclarativeBase):
    pass


item_author_association = Table(
    'item_author', Base.metadata,
    Column('author_id', Integer, ForeignKey('authors.id'), primary_key=True),
    Column('bibliography_key', Integer, ForeignKey('bibliography_items.key'), primary_key=True)
)

item_collection_association = Table(
    'item_collection', Base.metadata,
    Column('collection_id', Integer, ForeignKey('collections.id'), primary_key=True),
    Column('bibliography_key', Integer, ForeignKey('bibliography_items.key'), primary_key=True)
)

item_tag_association = Table(
    'item_tag', Base.metadata,
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True),
    Column('bibliography_key', Integer, ForeignKey('bibliography_items.key'), primary_key=True)
)

item_project_association = Table(
    'item_project', Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('bibliography_key', Integer, ForeignKey('bibliography_items.key'), primary_key=True)
)


class Author(Base):
    __tablename__ = 'authors'

    # Define columns for the table
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    firstName = mapped_column(String, nullable=True)
    lastName = mapped_column(String, nullable=True)

    items = relationship("BibliographyItem", secondary=item_author_association, back_populates="authors")

class BibliographyItem(Base):
    __tablename__ = 'bibliography_items'

    # Define columns for the table
    key = mapped_column(String, nullable=False, primary_key=True)
    zotero_key = mapped_column(String, nullable=True, unique=True)
    typeName = mapped_column(String, nullable=True)
    DOI = mapped_column(String, nullable=True)
    ISBN = mapped_column(String, nullable=True)
    title = mapped_column(String, nullable=True)
    date = mapped_column(String, nullable=True)
    year = mapped_column(Integer, nullable=True)
    series = mapped_column(String, nullable=True)
    journal = mapped_column(String, nullable=True)
    publisher = mapped_column(String, nullable=True)
    keywords = mapped_column(String, nullable=True)
    note = mapped_column(String, nullable=True)

    path = mapped_column(String, nullable=True)
    abstract = mapped_column(String, nullable=True)
    text = mapped_column(String, nullable=True)
    library_id = mapped_column(Integer, ForeignKey('libraries.id'))
    time_created = mapped_column(DateTime(timezone=True), server_default=func.now())
    time_updated = mapped_column(DateTime(timezone=True), onupdate=func.now())

    authors = relationship("Author", secondary=item_author_association, back_populates="items", lazy='joined')
    responses = relationship("Response", back_populates="item")
    collections = relationship('Collection', secondary=item_collection_association, back_populates="items", lazy='joined')
    projects = relationship('ProjectModel', secondary=item_project_association, back_populates="items")
    library = relationship("Library", back_populates="items", lazy='joined')
    tags = relationship('Tag', secondary=item_tag_association, back_populates="items", lazy='joined')


    @hybrid_property
    def authors_list(self):
        return [f'{author.lastName}, {author.firstName}' for author in self.authors]

    def __repr__(self):
        authors = '; '.join(self.authors_list)
        return f"<BibliographyEntry(key={self.key}, title={self.title}, authors={authors})>"


    def to_bibtex(self):
        pass

    def zotero_link(self):
        return f"zotero://select/items/{self.key}"

    @classmethod
    def to_df(cls, items):
        columns = [column.name for column in cls.__table__.columns]
        columns.extend([
            'authors_list',
            'library'
        ])

        data = []
        for item in items:
            data.append([getattr(item, column) for column in columns])

        df = pd.DataFrame(data, columns=columns).set_index('key')

        df.rename({
            'authors_list': 'authors'
            },
            axis=1,
            inplace=True
        )

        return df

    @property
    def formatted_text(self):
        s = f"{self.title}\n{', '.join(self.authors_list)}\n{self.year}\n\n{self.text}"
        return s

# QueryModel table
class QueryModel(Base):
    __tablename__ = 'queries'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False)#, unique=True)
    question = mapped_column(String, nullable=False)
    type = mapped_column(String, nullable=True)
    params = mapped_column(String, default='{}')
    project_id = mapped_column(Integer, ForeignKey('projects.id'))
    time_created = mapped_column(DateTime(timezone=True), server_default=func.now())
    time_updated = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to Response
    responses = relationship("Response", back_populates="query")
    project = relationship('ProjectModel', back_populates='queries')

    __table_args__ = (
        UniqueConstraint('name', 'project_id', name='_name_project_uc'),
    )

    def __repr__(self):
        return f"<QueryModel(id={self.id}, user_prompt='{self.question}', params={self.params})>"

    @property
    def prompt(self):
        params = self.load_params()
        return prompt_registry[self.type](question=self.question, **params)

    def load_params(self):
        params = json.loads(self.params)
        return params


class Response(Base):
    __tablename__ = 'responses'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    text = mapped_column(String, nullable=False)
    query_id = mapped_column(Integer, ForeignKey('queries.id'))
    item_key = mapped_column(String, ForeignKey('bibliography_items.key'))
    context = mapped_column(String, nullable=True)
    time_created = mapped_column(DateTime(timezone=True), server_default=func.now())
    time_updated = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    item = relationship("BibliographyItem", back_populates="responses")
    query = relationship("QueryModel", back_populates="responses")

    def __repr__(self):
        return f"<Response(id={self.id}, value={self.value}, text={self.text}, key='{self.item.key}', query_id={self.query.id})>"


    def get_list(self):
        l = re.findall(r'^\s*[*+-] (.+)$', self.text, flags=re.MULTILINE)
        return l

    def to_series(self):
        s = pd.Series({
            'text': self.text,
            'item_key': self.item_key,
            'query_od': self.query_id,
            'docs': self.get_list()
        }, name=self.id)
        return s

    @property
    def value(self):
        prompt = self.query.prompt
        value = prompt.parse_value(self.text)
        return value



class Library(Base):
    """
    Zotero Library / Group
    """
    __tablename__ = 'libraries'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False, unique=True)

    # Relationships
    items = relationship('BibliographyItem', back_populates="library")
    collections = relationship('Collection', back_populates='library')

    @classmethod
    def to_df(cls, libraries):
        columns = [column.name for column in cls.__table__.columns]

        data = []
        for library in libraries:
            data.append([getattr(library, column) for column in columns])

        df = pd.DataFrame(data, columns=columns).set_index('id')

        return df


class ProjectModel(Base):
    __tablename__ = 'projects'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False, unique=True)

    # Relationships
    items = relationship('BibliographyItem', secondary=item_project_association, back_populates="projects")#, lazy='joined')
    queries = relationship('QueryModel', back_populates='project')#, lazy='joined')



class Collection(Base):
    __tablename__ = 'collections'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False)
    parent_id = mapped_column(Integer, ForeignKey('collections.id'), nullable=True)
    library_id = mapped_column(Integer, ForeignKey('libraries.id'), nullable=True)

    # Relationships
    items = relationship('BibliographyItem', secondary=item_collection_association, back_populates="collections")
    parent = relationship('Collection', back_populates='children', remote_side=[id], lazy='joined')
    children = relationship('Collection', back_populates='parent')
    library = relationship('Library', back_populates='collections')

    def __repr__(self):
        return f"Collection(id={self.id}, name='{self.name}')"

    def get_items(self):
        items = self.items

        if self.children is not None:
            for child in self.children:
                items.extend(child.get_items())
        return items

    @property
    def path(self):
        if self.parent_id is None:
            return os.path.join(self.library.name, self.name)
        else:
            return os.path.join(self.parent.path, self.name)


class Tag(Base):
    __tablename__ = 'tags'

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False)

    # Relationships
    items = relationship('BibliographyItem', secondary=item_tag_association, back_populates="tags")

    def __repr__(self):
        return f"Tag(id={self.id}, name='{self.name}')"
