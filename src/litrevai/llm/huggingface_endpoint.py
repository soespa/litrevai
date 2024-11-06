from huggingface_hub import InferenceClient, ChatCompletionOutput

from .base import BaseLLM


class HuggingfaceModel(BaseLLM):

    def __init__(self, model=None, base_url=None, api_key=None):

        self.model = model

        self.client = InferenceClient(
            model=model,
            base_url=base_url,
            api_key=api_key
        )

    def generate_text(
            self,
            messages,
            prefix_function=None,
            temperature=0.6,
            max_new_tokens=2048,
            top_p=0.9
    ) -> str | None:
        output: ChatCompletionOutput = self.client.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_new_tokens,
            top_p=top_p
        )

        answer = output.choices[0].message.content

        return answer