import openai
from openai import OpenAI

from litrevai.llm import BaseLLM


class OpenAIModel(BaseLLM):

    def __init__(self, model=None, api_key=None):
        """
        Initialize the OpenAI model client.

        Args:
            model (str): The model name (e.g., 'gpt-3.5-turbo').
            api_key (str): Your OpenAI API key.
        """
        self.model = model
        openai.api_key = api_key  # Set the OpenAI API key


        self.client = OpenAI(
            api_key=api_key
        )

    def generate_text(
            self,
            messages,
            temperature=0.6,
            max_tokens=2048,
            top_p=0.9
    ) -> str | None:
        """
        Generate text based on the provided messages using OpenAI's API.

        Args:
            messages (list): A list of messages to send to the model.
            temperature (float): Sampling temperature.
            max_tokens (int): The maximum number of tokens to generate.
            top_p (float): Nucleus sampling parameter.

        Returns:
            str | None: The generated text or None if the generation fails.
        """
        try:
            # Call OpenAI's chat completion API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p
            )

            # Extract the generated text from the response
            answer = response.choices[0].message.content

            return answer

        except Exception as e:
            print(f"Error generating text: {e}")
            return None


