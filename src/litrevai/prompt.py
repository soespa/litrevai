import json
import re
import importlib.resources
from typing import List, Mapping

package_name = __package__



prompt_registry = {}


def register_prompt(cls):
    prompt_registry[cls.name] = cls
    return cls


class Prompt:
    name: str = 'default'
    system_prompt: str
    question: str
    params: dict = {}

    def __init__(self, question, **params):
        """
        Base class for all prompts.

        :param question: The question or command used for RAG.
        :param params:
        """
        self.question = question
        self.params = params
        self.system_prompt = self._load_system_prompt()
        self.search_phrase = question

        if 'concept' in params:
            concept = params.get('concept')
            self.system_prompt = self.system_prompt + f"\nConsider the following definition: {concept}\n"

        if 'examples' in params:
            examples = params.get('examples')
            self.system_prompt = self.system_prompt + f"\nConsider the following examples: {examples}\n"

        if 'search_phrase' in params:
            search_phrase = params.get('search_phrase')
            self.search_phrase = search_phrase

    def _load_system_prompt(self):
        if package_name is None:
            with open(f'data/prompts/{self.name}.txt', 'r') as f:
                return f.read()

        with importlib.resources.open_text(package_name + '.data.prompts', f'{self.name}.txt') as file:
            return file.read()

    def parse_value(self, answer):
        return answer

    def messages(self, context):
        messages = [
            {
                'role': 'system',
                'content': self.system_prompt
            },
            {
                'role': 'user',
                'content': f'Question: {self.question}\n\nContext: {context}\n\n"'
            }
        ]
        return messages


@register_prompt
class YesNoPrompt(Prompt):
    """
    Prompt that is to be answered by yes or no. Can be used as a filter. For finer-detailed answers use LikertPrompt.
    """
    name: str = 'yes_no'

    def __init__(self, question: str, **params):
        super().__init__(question, **params)

    def parse_value(self, answer) -> bool | None:
        answer = answer.strip().lower()

        if answer.startswith('yes'):
            return True
        elif answer.startswith('no'):
            return False
        return None


@register_prompt
class ListPrompt(Prompt):
    """
    Prompt that returns a list of items.
    """
    name: str = 'list'
    n: int = 5

    def __init__(self, question: str, n=5, **params):
        """

        :param question: Question asking for the list items. Example::
            "What learning objectives related to programming are mentioned in the context?"
        :param n: (Maximum) number of bullet point items asked for.
        :param params: See Prompt.
        """

        self.n = n
        params['n'] = n

        super().__init__(question, **params)
        self.system_prompt = self.system_prompt.format(self.n)

    def parse_value(self, answer) -> List[str]:
        return re.findall(r'^[-*+0-9]\.? (.+)$', answer, flags=re.MULTILINE)


@register_prompt
class OptionsPrompt(Prompt):
    """
    Prompt that is used to choose from a set of options. Useful for classification

    """
    name: str = 'options'
    options: dict

    def __init__(self, question: str, options: Mapping[str, str], **params):
        """

        :param question:
        :param options: Dict with the options to choose from as keys and a description of each option as the value.
        :param params:
        """

        self.options = options
        params['options'] = options
        super().__init__(question, **params)

        options_string = '\n'.join([f'- **{key}**: {value}' for key, value in self.options.items()])
        self.system_prompt = self.system_prompt.format(options_string)

    def parse_value(self, answer) -> str:

        for option in self.options:
            if option.lower() in answer.lower():
                return option
        return None


@register_prompt
class LikertPrompt(Prompt):
    """
    A Liker-like Question that allows for different levels of agreement.
    """
    name: str = 'likert'
    scale: dict = {
        -3: "Strongly Disagree",
        -2: "Disagree",
        -1: "Somewhat Disagree",
         0: "Neutral",
         1: "Somewhat Agree",
         2: "Agree",
         3: "Strongly Agree"
    }

    def __init__(self, question: str, **params):
        super().__init__(question, **params)

        if 'scale' in params:
            self.scale: dict = params.get('scale')

        scale_string = '\n'.join([f'- **{key}**: {value}' for key, value in self.scale.items()])
        self.system_prompt = self.system_prompt.format(scale=scale_string)


    def messages(self, context):
        messages = [
            {
                'role': 'system',
                'content': self.system_prompt
            },
            {
                'role': 'user',
                'content': f'Statement: {self.question}\n\nContext: {context}\n\n"'
            }
        ]
        return messages

    def parse_value(self, answer):

        match = re.search(r'-?[0-9]+', answer)

        if match:
            return int(match.group(0))


        return None


@register_prompt
class OpenPrompt(Prompt):
    """
    Open Question that can be answered in a few sentences.
    """
    name: str = 'open'
    n_sentences: int = 3

    def __init__(self, question: str, **params):
        super().__init__(question, **params)

        if 'n_sentences' in params:
            self.n_sentences = params.get('n_sentences')

        self.system_prompt = self.system_prompt.format(n_sentences=self.n_sentences)

    def parse_value(self, answer):
        return answer


@register_prompt
class CriteriaPrompt(Prompt):
    """
    """
    name: str = 'criteria'
    criteria: Mapping[str, str]

    def __init__(self, question: str, criteria: Mapping[str, str], **params):

        self.criteria = criteria
        params['criteria'] = criteria

        super().__init__(question, **params)

        criteria_string = '\n'.join([f'- **{key}**: {value}' for key, value in self.criteria.items()])
        self.system_prompt = self.system_prompt.format(criteria=criteria_string)


    def messages(self, context):
        messages = [
            {
                'role': 'system',
                'content': self.system_prompt
            },
            {
                'role': 'user',
                'content': f'Question: {self.question}\n\nContext: {context}\n\n"'
            }
        ]
        return messages

    def parse_value(self, answer):

        match = re.search(r'\{.+\}', answer, flags=re.DOTALL)

        if match:
            try:
                d = json.loads(match.group(0))
                return d
            except Exception as e:
                print(e)
                return None


        return None



class CustomPrompt(Prompt):
    """
        """
    name: str = 'custom'

    def __init__(self, system_prompt: str, question: str, **params):

        self.system_prompt = system_prompt

        super().__init__(question, **params)


    def _load_system_prompt(self):
        return self.system_prompt

    def messages(self, context):
        messages = [
            {
                'role': 'system',
                'content': self.system_prompt
            },
            {
                'role': 'user',
                'content': f'Question: {self.question}\n\nContext: {context}\n\n"'
            }
        ]
        return messages

    def parse_value(self, answer):

        return answer


@register_prompt
class ListExtractionPrompt(Prompt):
    """
    """
    name: str = 'list_extraction'

    def __init__(self, question: str, examples: List[str] | None = None, **params):

        super().__init__(question, **params)

        examples_string = ''

        if examples:
            self.examples = examples
            params['example'] = examples

            examples_string = '\n'.join([f'- {example}' for example in self.examples])
            examples_string = '**Examples**:\n' + examples_string

        self.system_prompt = self.system_prompt.format(examples=examples_string)


    def messages(self, context):
        messages = [
            {
                'role': 'system',
                'content': self.system_prompt
            },
            {
                'role': 'user',
                'content': f'Question: {self.question}\n\nContext: {context}\n\n"'
            }
        ]
        return messages

    def parse_value(self, answer):

        match = re.search(r'\{.+\}', answer, flags=re.DOTALL)

        if match:
            try:
                d = json.loads(match.group(0))
                return d
            except Exception as e:
                print(e)
                return None


        return None