import sys

sys.path.append('../src')

from litrevai import OpenAIModel, HuggingfaceModel

import pytest


messages = [{
    'role': 'user',
    'content': 'What is the capital of france?'
}]

@pytest.mark.skip(reason="No Huggingface configured.")
def test_hf():
    model = HuggingfaceModel()

    answer = model.generate_text(messages=messages)

    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0


def test_openai():
    model = OpenAIModel()

    answer = model.generate_text(messages=messages)

    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0
