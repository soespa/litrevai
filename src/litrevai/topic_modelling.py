import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
import pandas as pd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.feature_extraction.text import CountVectorizer
from hdbscan import HDBSCAN
from .llm import BaseLLM


class TopicModel:
    """
    Wrapper for BERTopic.

    """

    embeddings = None
    _items: pd.DataFrame
    df: pd.DataFrame

    def __init__(self, question, items, responses, llm: BaseLLM | None = None, embeddings_model="BAAI/bge-large-en-v1.5", **kwargs):

        self.question = question
        self._items = items

        if llm:
            self.llm = llm

        nltk.download('stopwords', quiet=True)

        self.responses = responses
        self.embedding_model = SentenceTransformer(embeddings_model, trust_remote_code=True)

        self._recalculate_embeddings()

        self.fit_model(**kwargs)


    @property
    def items(self):
        return self._items


    def _repr_markdown_(self):
        md = ''

        for i, topic in self.topics.iterrows():

            n = topic['count']

            md += f'**{topic.label}** (n={n})\n\n'
            md += f'**Keywords:** {", ".join(topic.keywords)}\n\n'
            md += f'**Examples:**\n\n'
            for example in topic.examples:
                md += f'- {example}\n'
            md += '\n\n'

        return md

    def get_document_info(self):
        """
        Gets all documents together with the corresponding topic and
        :return:
        """

        columns = ['title', 'year', 'DOI', 'typeName', 'series', 'journal']
        items = self.items[columns]
        df = items.loc[self.responses.index.get_level_values(0)].reset_index(names='key')
        document_info = self.topic_model.get_document_info(self.docs, df=df)

        return document_info

    def get_responses_for_topic(self, topic_id):
        topics = self.topic_model.topics_

        df = self.responses.to_frame(name='response')

        df.loc[:, 'topic'] = topics
        df = df[df['topic'] == topic_id]

        return df

    def get_items_for_topic(self, topic_id):
        """
        Return all items that have at least one mention of the topic
        :param topic_id:
        :return:
        """
        df = self.get_responses_for_topic(topic_id)

        df = df.groupby(level=0).apply(lambda s: pd.Series({
            'responses': s['response'].to_list(),
            'n': len(s)
        }))

        items = df.join(self.items, how='left')

        return items



    def merge_topics(self, topics_to_merge):

        self.topic_model.merge_topics(
            docs=self.docs,
            topics_to_merge=topics_to_merge
        )

        topics = self.topic_model.topics_

        df = self.responses.to_frame()
        df.loc[:, 'topic'] = topics
        self.df = df

        self.generate_names()


    def _recalculate_embeddings(self):
        self.embeddings = self.embedding_model.encode(
            self.docs,
            show_progress_bar=True
        )

    def interact(self):

        from ipywidgets import interact_manual, fixed, widgets

        docs = self.docs
        n = len(docs)

        interact_manual(
            self.fit_model,
            min_cluster_size=widgets.IntSlider(min=2, max=n, step=1, value=2, description_tooltip='Minimal size for a cluster to form'),
            min_samples=widgets.IntSlider(min=1, max=n, step=1, value=1, description_tooltip='Should be smaller than min_cluster size'),
            seed_topic_list=fixed(None),
            language=fixed('en'),
            min_df=(1, n),
            max_df=(0.0, 1.0, 0.01),
            n_components=fixed(5),
            n_neighbors=fixed(15),
            cluster_selection_method=widgets.Dropdown(options=['leaf', 'eom'], value='leaf')
        )

    def fit_model(
            self,
            min_cluster_size=5,
            min_samples=None,
            n_neighbors=15,
            n_components=5,
            cluster_selection_method='leaf',
            language='english',
            seed_topic_list=None,
            min_df=1,
            max_df=0.8,
    ):

        stop_words = list(stopwords.words('english'))

        umap_model = UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            min_dist=0.1,
            metric='cosine',
            random_state=42,
        )

        vectorizer_model = CountVectorizer(
            stop_words=stop_words,
            min_df=min_df,
            max_df=max_df,
            ngram_range=(1, 3)
        )

        hdbscan_model = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric='euclidean',
            cluster_selection_method=cluster_selection_method,
            prediction_data=True
        )

        topic_model = BERTopic(
            embedding_model=self.embedding_model,
            umap_model=umap_model,
            #umap_model=empty_dimensionality_model,
            vectorizer_model=vectorizer_model,
            hdbscan_model=hdbscan_model,
            language=language,
            top_n_words=20,
            verbose=False,
            calculate_probabilities=True,
            # nr_topics=15
            seed_topic_list=seed_topic_list
        )
        topics, probs = topic_model.fit_transform(self.docs, self.embeddings)

        self.topic_model = topic_model

        df = self.responses.to_frame()
        df.loc[:, 'topic'] = topics
        self.df = df

        self.generate_names()


    def generate_names(self, n=20):

        s = ''

        for index, row in self.topic_model.get_topic_info().iloc[1:n+1].iterrows():
            s += f'Topic {row["Topic"]}\n'
            keywords = ', '.join(row['Representation'])
            s += f'Keywords: {keywords}\n\n'
            examples = '\n'.join(['- ' + doc for doc in row['Representative_Docs']])
            s += f'Examples:\n{examples}\n\n'


        messages = [
            {
                'role': 'system',
                'content': f"""You are a helpful assistant.
Using the information below, find a label for each of the topics presented.
The topics were retrieved bases on the prompt: {self.question}
Give your answer as JSON with the numbers of the topic as the keys:"""
            },
            {
                'role': 'user',
                'content': s
            }
        ]

        answer = self.llm.generate_text(messages)

        match = re.search(r'\{.*\}', answer, flags=re.DOTALL)

        if match:
            try:
                topic_labels = json.loads(match.group(0))
            except Exception as e:
                print('Generating labels failed, due to incorrect json format from the LLM.')
                return

            topic_labels = {int(key): f"{key} {value}" for key, value in topic_labels.items()}

            topic_labels[-1] = '-1 Outlier'

            self.topic_model.set_topic_labels(topic_labels)

            return topic_labels


    def summary(self) -> str:
        """
        Returns a string that contains a comprehensive list of all topics including their generated names,
        the keywords representing the topics and a list of representative examples for that topic.
        :return:
        """
        topics = self.topics

        s = ''

        for i, topic in topics.iterrows():

            n = topic['count']

            s += f'Topic {i}: {topic.label} (n={n})\n'
            s += f'Keywords: {", ".join(topic.keywords)}\n'
            s += f'Examples:\n'
            for example in topic.examples:
                s += f'- {example}\n'
            s += '\n\n'

        return s

    def visualize_documents(self, title=None):

        fig = self.topic_model.visualize_documents(
            self.docs,
            custom_labels=True,
            hide_annotations=True,
            title=title
        )

        fig.show()

    @property
    def topic_labels(self):
        return self.topics['label'].to_dict()

    def topic_distribution(self, normalize=False, include_outlier=False):
        items_topics_matrix = self.items_topics_matrix()

        total = items_topics_matrix.sum()

        if not include_outlier:
            total = total.drop(-1)

        if normalize:
            total = total / total.sum()

        return total

    def visualize_topic_distribution(self, normalize=False, include_outlier=False, title='Topic Distribution'):

        items_topics_matrix = self.items_topics_matrix()

        total = items_topics_matrix.sum()

        if not include_outlier:
            total = total.drop(-1)

        if normalize:
            total = total / total.sum()

        rename = self.topic_labels

        total = total.to_frame(name='# Items')

        total['Label'] = total.rename(rename).index

        fig = px.pie(total, values='# Items', names='Label', hole=.3, title=title)

        return fig


    def visualize_hierarchy(self, title='Hierarchical Clustering', **kwargs):
        hierarchical_topics = self.topic_model.hierarchical_topics(self.docs, **kwargs)
        fig = self.topic_model.visualize_hierarchy(
            hierarchical_topics=hierarchical_topics,
            custom_labels=True,
            title=title,
            **kwargs
        )
        return fig



    def items_topics_matrix(self, bool_only=False) -> pd.DataFrame:
        """
        Returns a dataframe where each row represents an item and each column represents a topic.
        The number represents if / how often the topic is present in that item.

        :param bool_only: Limits the values to True if the topic is present and False if it is not present in the item.
        :return:
        """
        df = self.df

        matrix = df.groupby(level=0)['topic'].value_counts().unstack().fillna(0).astype(int)

        if bool_only:
            matrix = matrix > 0

        matrix.index.name = 'key'

        return matrix


    @property
    def topics(self):

        temp = self.topic_model.get_topic_info()

        rename = {
            'Topic': 'topic',
            'CustomName': 'label',
            'Representation': 'keywords',
            'Representative_Docs': 'examples',
            'Count': 'count'
        }

        temp = temp.rename(rename, axis=1).set_index('topic')

        temp = temp[['label', 'keywords', 'examples', 'count']]

        return temp

    @property
    def docs(self):
        return self.responses.to_list()

    def __repr__(self):
        return str(self.topics)


    def save(self, path):
        self.topic_model.save(path, serialization="safetensors", save_ctfidf=True)

    def topics_over_time(self, normalize=False, include_outliers=False):

        itm = self.items_topics_matrix()

        total = itm.join(self.items['year']).groupby('year').sum()

        if not include_outliers:
            total = total.drop(-1, axis=1)

        if normalize:
            total = total.div(total.sum(axis=1), axis=0)



        return total

    def set_topic_labels(self, topic_labels):
        self.topic_model.set_topic_labels(topic_labels)

    def visualize_topics_over_time(self, normalize=False, include_outliers=False, title=None):

        topic_labels = self.topic_labels

        total = self.topics_over_time(normalize=normalize, include_outliers=include_outliers)

        total = total.rename(topic_labels, axis=1)

        fig = px.line(total, title=title, height=500, width=1000)

        fig.update_xaxes(title='Year')

        if normalize:
            y_axes_title = 'Percentage [%]'
        else:
            y_axes_title = '# Items'

        fig.update_yaxes(title=y_axes_title)
        fig.update_legends(title='Topic')

        fig.update_layout(margin=dict(t=50, b=10, r=10, l=10))

        return fig
