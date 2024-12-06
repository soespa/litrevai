import sys
sys.path.append('../src')

import pytest
import pandas as pd
from litrevai import LiteratureReview, OpenPrompt, ListPrompt, OpenAIModel
from litrevai.project import Project
from litrevai.query import Query
from litrevai.topic_modelling import TopicModel
import importlib.resources


@pytest.fixture(scope="session")
def db(tmpdir_factory):
    fn = tmpdir_factory.mktemp("db")
    lr = LiteratureReview(fn)
    return fn


project_name = "New Project"

def test_import_documents(db):
    lr = LiteratureReview(db)

    path = importlib.resources.path('tests.data.bibliography_example', 'references.bib')
    lr.import_bibtex(path)

    items = lr.items

    assert 'hoperLearningExplanatoryModel2024' in items.index


def test_create_project(db):

    lr = LiteratureReview(db)

    project_name = "New Project"

    project = lr.create_project(project_name)

    assert isinstance(project, Project)

    project.add_items(lr.items)

    project = lr.projects.get(project_name)

    assert isinstance(project, Project)

    items = project.items

    assert isinstance(items, pd.DataFrame)
    assert 'title' in items.columns
    assert len(items) > 0
    assert len(items.iloc[0].text) > 0

def test_create_query(db):
    lr = LiteratureReview(db)

    project = lr.projects.get(project_name)

    prompt = ListPrompt(
        question="What is the article about?",
        n=10
    )

    query_name = "New Query"

    query = project.create_query(
        name=query_name,
        prompt=prompt
    )

    query = project.queries.get(query_name)

    assert isinstance(query, Query)

    llm = OpenAIModel()
    lr.set_llm(llm)

    query.run()

    print(query.responses)

    assert isinstance(query.responses, pd.Series)

    assert len(query.responses) > 0


# def test_topic_model(db):
#     lr = LiteratureReview(db)
#
#     project_name = "New Project"
#
#     project = lr.projects.get(project_name)
#
#     query_name = "New Query"
#
#     query = project.queries.get(query_name)
#
#     topic_model = query.create_topic_model()
#
#     assert isinstance(topic_model, TopicModel)



# def test_import_zotero(db):
#
#     lr = LiteratureReview(db)
#     lr.import_zotero(filter_type_names=['journalArticle', 'conferencePaper'], filter_libraries=["Personal"])

def test_delete_projects(db):

    lr = LiteratureReview(db)

    for name, project in lr.projects.items():
        lr.delete_project(name)

    assert len(lr.projects) == 0