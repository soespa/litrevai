
import pytest

def test_hf():
    from litrevai.llm import HuggingfaceModel

    model = HuggingfaceModel()

    assert model is not None



def test_openai():
    from litrevai.llm import OpenAIModel
    model = OpenAIModel()

    assert model is not None
