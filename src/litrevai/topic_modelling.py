import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import re
import nltk
from bertopic.dimensionality import BaseDimensionalityReduction
from nltk.corpus import stopwords
import pandas as pd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.feature_extraction.text import CountVectorizer
from hdbscan import HDBSCAN
from .llm import BaseLLM


class TopicModel:
    _embeddings = None
    topic_model: BERTopic
    _items: pd.DataFrame
    df: pd.DataFrame

    def __init__(self, items, responses, llm: BaseLLM | None = None, embeddings_model="BAAI/bge-large-en-v1.5", **kwargs):

        self._items = items

        if llm:
            self.llm = llm

        nltk.download('stopwords', quiet=True)

        responses = responses[~responses.isna()]

        if isinstance(responses.iloc[0], list):
            responses = responses.explode()

        responses.name = 'response'

        self.responses = responses[~responses.isna()]
        self.embedding_model = SentenceTransformer(embeddings_model, trust_remote_code=True)

        self.fit_model(**kwargs)

    @property
    def items(self):
        return self._items

    def get_items_for_topic(self, topic_id):
        """
        Return all items that have at least one mention of the topic
        :param topic_id:
        :return:
        """
        topics = self.topic_model.topics_

        df = self.responses.to_frame(name='response')

        df.loc[:, 'topic'] = topics
        df = df[df['topic'] == topic_id]

        items = df.join(self.items, how='left')

        return items


    def exclude_responses_with_topic(self, topic_id):
        df = self.df

        df = df[df['topic'] != topic_id]

        responses = self.responses

        responses = responses.loc[df.index]

        self.responses = responses

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = self.embedding_model.encode(
                self.docs,
                show_progress_bar=True
            )
        return self._embeddings


    def interactive_model(self):

        from ipywidgets import interact

        docs = self.docs
        n = len(docs)

        return interact(self.fit_model, min_cluster_size=(2, n))

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

    def hierarchy(self):

        topic_model = self.topic_model
        docs = self.docs

        hierarchical_topics = topic_model.hierarchical_topics(docs)
        fig = topic_model.visualize_hierarchy(hierarchical_topics=hierarchical_topics, custom_labels=True)
        return fig

    def generate_names(self):

        s = ''

        for index, row in self.topic_model.get_topic_info().iloc[1:].iterrows():
            s += f'Topic {row["Topic"]}\n'
            keywords = ', '.join(row['Representation'])
            s += f'Keywords: {keywords}\n\n'
            examples = '\n'.join(['- ' + doc for doc in row['Representative_Docs']])
            s += f'Examples:\n{examples}\n\n'

        print(len(s))

        s = s[:10000]

        messages = [
            {
                'role': 'system',
                'content': """You are a helpful assistant.
Using the information below, find a label for each of the topics presented.
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
            topic_labels = json.loads(match.group(0))

            topic_labels = {int(key): value for key, value in topic_labels.items()}

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
    def items_topics_matrix(self, bool_only=False) -> pd.DataFrame:
        """
        Returns a dataframe where each row represents an item and each column represents a topic.
        The number represents if / how often the topic is present in that item.

        :param bool_only: Limits the values to True if the topic is present and False if it is not present in the item.
        :return:
        """
        df = self.df

        matrix = df.groupby(df.index)['topic'].value_counts().unstack().fillna(0).astype(int)

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
        return self.topics

    @property
    def propabilities(self):

        topic_model = self.topic_model
        topic_labels = topic_model.custom_labels_
        #docs = self.docs

        responses = self.responses

        probs = pd.DataFrame(topic_model.probabilities_, index=responses.index)
        probs = probs.rename(topic_labels, axis=1)
        probs['Other'] = 1 - probs.sum(axis=1)

        probs = probs.groupby('doi').mean()

        return probs

    def save(self, path):
        self.topic_model.save(path, serialization="safetensors", save_ctfidf=True)

    def topics_over_time(self):

        probs = self.propabilities

        time_series = probs.join(self.items['year'], how='left', on='doi')

        # time_series['year'] = pd.to_datetime(time_series['year'], format='%Y')

        time_series['year'] = time_series['year'].astype(int)

        time_series = time_series.groupby('year').mean() * 100

        time_series = time_series.drop('Other', axis=1)

        fig = px.line(time_series, title='Relevance of Rationales over Time', height=500, width=1000)

        fig.update_xaxes(title='Year')
        fig.update_yaxes(title='Relevancy [%]', range=(0, 15))
        fig.update_legends(title='Rationale')

        fig.update_layout(margin=dict(t=50, b=10, r=10, l=10))

        fig.show()

        fig.write_image('figures/rationales_over_time.pdf')
