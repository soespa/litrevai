# LitRevAI

[![PyPI - Version](https://img.shields.io/pypi/v/litrevai.svg)](https://pypi.org/project/litrevai)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/litrevai.svg)](https://pypi.org/project/litrevai)

-----


**Table of Contents**

- [Description](#description)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Large Language Models](#large-language-models)
- [License](#license)

## Description

**LitRevAI** (Literature Review AI) is a Python package designed to
automate systematic literature reviews using natural language processing (NLP) techniques.
It supports the import of documents from Zotero, including metadata, for streamlined analysis.
By integrating Retrieval-Augmented Generation with advanced topic modeling
via [BERTopic](https://github.com/MaartenGr/BERTopic), LitRevAI offers a powerful tool for efficient,
data-driven literature reviews.

## Installation

```console
pip install litrevai
```

## Basic Usage
Using **LitRevAI** typically follows these steps:

1. **Import Documents**: Load documents, including metadata, from Zotero or other sources.
2. **Create a Project**: Set up a new project to organize and analyze your literature review.
3. **Add Documents to the Project**: Include the imported documents in the project for analysis.
4. **Create a Query**: Formulate a query to retrieve relevant information from the documents.
5. **Run the Query**: Apply the query across all documents in the project to gather responses.
6. **Refine or Analyze**: Use the responses to either ask additional questions or generate a topic model.

### RAG

```python
from litrevai import LiteratureReview, YesNoPrompt, ListPrompt, HuggingfaceModel

# Access Database
lr = LiteratureReview('db')

# Import Documents from Zotero Personal Library
lr.import_zotero(filter_libraries=['Personal'])

# Create a project
project = lr.create_project(name='New Project')

# Add all items to the project
project.add_items(lr.items)

# Create a query using a YesNoPrompt
prog_query = project.create_query(
    name='programming',
    prompt=YesNoPrompt(
        question="Does the document report on a study or experiment involving programming?"
    )
)

# Running a query requires to define an inference model
model = HuggingfaceModel(model='meta-llama/Llama-3.1-8B-Instruct')
lr.set_llm(model)

# Run query over all documents in the project
prog_query.run()

print(prog_query.responses)

# Create another Query
concept_query = project.create_query(
    name='prog_concepts',
    prompt=ListPrompt(
        question="What programming concepts are mentioned in the document? List all of them!",
        n=10
    )
)

# Use the responses from the last query as a filter
concept_query.run(items=prog_query.as_filter())

print(concept_query.responses)
```

### Topic Modelling

```python
from litrevai import LiteratureReview

lr = LiteratureReview('db')

query = lr.queries['prog_concepts']

topic_model = query.create_topic_model()

topic_model.summary()
```


### Full-Text Search

```python
df = project.search('Epistemic Programming')
df
```


## Large Language Models

To use Retrieval-Augmented Generation (RAG) or topic modeling in **LitRevAI** a large language model (LLM) is required.
LitRevAI provides basic support for LLM inference via Huggingface and OpenAI.
To enable these integrations, it’s recommended to store the required API keys either in an `.env` file within
the working directory or in environment variables.

```
HF_TOKEN=""
OPENAI_API_KEY=""
```

Alternatively, you can pass them directly to the constructor:

```python
from litrevai.llm import HuggingfaceModel, OpenAIModel

api_key = 'xy'
model = 'model_name_or_url'

model = HuggingfaceModel(api_key=api_key, model=model)
model = OpenAIModel(api_key=api_key, model=model)
```

## License

`litrevai` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
