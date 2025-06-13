import os

import openai
from openai import OpenAI

from litrevai.llm import BaseLLM


class OpenAIModel(BaseLLM):

    def __init__(self, model=None, base_url=None, api_key=None, **kwargs):
        """
        Initialize the OpenAI model client.

        Args:
            model (str): The model name (e.g., 'gpt-3.5-turbo').
            api_key (str): Your OpenAI API key.
        """

        super().__init__()

        if model is None:
            model = os.getenv('OPENAI_MODEL', None)
        if api_key is None:
            api_key = os.getenv('OPENAI_API_KEY', '')
        if base_url is None:
            base_url = os.getenv('OPENAI_BASE_URL', None)

        self.model = model
        self.api_key = api_key
        self.base_url = base_url

        #openai.api_key = api_key  # Set the OpenAI API key

        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            **kwargs
        )

    def generate_text(
            self,
            messages,
            temperature=0.6,
            max_new_tokens=2048,
            top_p=0.9
    ) -> str | None:
        """
        Generate text based on the provided messages using OpenAI's API.
        """
        try:
            # Call OpenAI's chat completion API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_new_tokens,
                top_p=top_p,
                #tool_choice="auto"
            )

            # Extract the generated text from the response
            answer = response.choices[0].message.content

            return answer

        except Exception as e:
            raise e
            print(f"Error generating text: {e}")
            return None


