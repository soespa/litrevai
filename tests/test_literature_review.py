import pytest
import pandas as pd
from litrevai import LiteratureReview, OpenPrompt
from litrevai.project import Project
from litrevai.query import Query


@pytest.fixture(scope="session")
def db(tmpdir_factory):
    fn = tmpdir_factory.mktemp("db")
    lr = LiteratureReview(fn)
    return fn

def test_delete_projects(db):

    lr = LiteratureReview(db)

    for name, project in lr.projects.items():
        lr.delete_project(name)

    assert len(lr.projects) == 0

def test_create_project(db):

    lr = LiteratureReview(db)

    project_name = "New Project"

    project = lr.create_project(project_name)

    assert isinstance(project, Project)

    project = lr.projects.get(project_name)

    lr.import_bibtex('./example_data/zotero_example.bib', project)

    items = project.items

    assert isinstance(items, pd.DataFrame)
    assert 'title' in items.columns
    assert len(items) > 0
    assert len(items.iloc[0].text) > 0

    prompt = OpenPrompt(question="What is the article about?")

    query_name = "New Query"

    query = project.create_query(
        name=query_name,
        prompt=prompt
    )

    query = project.queries.get(query_name)

    assert isinstance(query, Query)


def test_import_zotero(db):

    lr = LiteratureReview(db)

    lr.import_zotero(filter_type_names=['journalArticle', 'conferencePaper'], filter_libraries=["My library"])