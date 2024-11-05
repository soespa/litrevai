import json
from typing import List, TYPE_CHECKING

import pandas as pd

from .prompt import Prompt
from .schema import QueryModel
from .topic_modelling import TopicModel
from .util import resolve_items

if TYPE_CHECKING:
    from .literature_review import LiteratureReview


class Query:
    """
    A query is like a task to be performed as part of a project.
    It consists of a prompt and is identified by a (unique) name.
    When a query is run on an item, a Response object is created,
    which stores the answer to the query for that item.
    """

    _query_id: int

    def __init__(self, lr: 'LiteratureReview', query_id: int):
        self.lr = lr
        self.db = self.lr.db
        self._query_id = query_id
        self.Session = self.db.Session

    @property
    def name(self):
        return self._query_model.name

    @property
    def prompt(self) -> Prompt:
        return self._query_model.prompt

    @property
    def params(self):
        return self.prompt.params

    @property
    def question(self):
        return self._query_model.question

    @property
    def prompt_type(self):
        return self._query_model.type

    def clear_responses(self):
        with self.Session() as session:
            self.db.clear_responses(session, self.query_id)

            session.commit()

    def update_prompt(self, prompt):
        with self.Session() as session:
            query = session.get(QueryModel, self.query_id)
            query.question = prompt.question
            query.type = prompt.name
            query.params = json.dumps(prompt.params)

            self.db.clear_responses(session, self.query_id)

            session.commit()

    def as_filter(self, value=True) -> List[str]:
        """
        Return all item keys, where the value of the responses to the query are equal to the specified value.
        :param value:
        :return:
        """
        responses = self.responses
        keys = list(responses[responses == value].index)
        return keys

    @property
    def query_id(self):
        return self._query_id

    @property
    def responses(self):
        return self.db.get_responses_for_query(self.query_id)

    @property
    def _query_model(self):
        with self.Session() as session:
            query_model = self.db.get_query_by_id(session, self.query_id)
        return query_model

    @property
    def project(self):
        from .project import Project
        project = Project(self.lr, self._query_model.project_id)
        return project

    def interactive_labelling(self):
        import ipywidgets as widgets
        from IPython.display import display

        responses = self.project.responses

        # Initial texts and labels
        texts = responses.to_list()

        # Predefined list of labels
        predefined_labels = ["Positive", "Negative", "Neutral"]

        # Variables to keep track of the current text index and labels
        current_text_index = 0
        current_labels = predefined_labels.copy()

        # Label dropdown
        label_dropdown = widgets.Dropdown(
            options=current_labels,
            description='Label:',
        )

        # Text area for new label
        new_label_text = widgets.Text(
            placeholder='Add a new label...',
            description='New Label:',
        )

        new_label_button = widgets.Button(
            description='Add label'
        )

        # Text display area
        text_display = widgets.Textarea(
            value=texts[current_text_index],
            description='Text:',
            layout=widgets.Layout(width='100%', height='80px'),
            disabled=True
        )

        # Button to submit the label
        submit_button = widgets.Button(
            description="Submit Label",
            button_style='success'
        )

        # Button to load the next text
        next_text_button = widgets.Button(
            description="Next Text",
            button_style='primary',
        )

        # Output area to display feedback
        output = widgets.Output()

        # Function to handle label submission
        def submit_label(change):
            with output:
                output.clear_output()
                selected_label = label_dropdown.value
                print(f"Labeled as: {selected_label}")

        # Function to handle adding a new label
        def add_new_label(change):
            new_label = new_label_text.value.strip()
            if new_label and new_label not in current_labels:
                current_labels.append(new_label)
                label_dropdown.options = current_labels
                new_label_text.value = ""  # Clear the text input

        # Function to load the next text
        def load_next_text(value):
            global current_text_index
            current_text_index = (current_text_index + 1) % len(texts)
            text_display.value = texts[current_text_index]
            with output:
                output.clear_output()
                print("Loaded new text for labeling.")

        # Set up event handlers
        submit_button.on_click(submit_label)
        next_text_button.on_click(load_next_text)
        new_label_button.on_click(add_new_label)

        # Display all widgets
        display(widgets.VBox([
            text_display,
            widgets.HBox([label_dropdown, new_label_text, new_label_button]),
            widgets.HBox([submit_button, next_text_button]),
            output
        ]))

    def run(self, items: List[str] | pd.DataFrame | None = None):
        include_keys = resolve_items(items)

        self.lr.run_query(self.query_id, include_keys=include_keys)

    def test(self):
        self.lr.test_query(self.query_id)

    def create_topic_model(self, **kwargs):
        topic_model = TopicModel(
            items=self.project.items,
            responses=self.responses,
            llm=self.lr.llm,
            **kwargs
        )
        return topic_model

    def __repr__(self):
        model = self._query_model
        return f"Query(\"{model.question}\", type={self.prompt_type})"