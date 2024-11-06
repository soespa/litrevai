import os
import requests
from litrevai.llm import BaseLLM


class CustomEndpoint(BaseLLM):


    def __init__(self, endpoint_url=None, api_key=None):
        if not api_key:
            api_key = os.getenv('API_KEY')

        if not endpoint_url:
            endpoint_url = os.getenv('ENDPOINT_URL')

            if endpoint_url is None:
                raise Exception('No Endpoint URL specified.')

        self.endpoint_url = endpoint_url
        self.api_key = api_key

        self.session = requests.Session()

    def generate_text(
            self,
            messages,
            prefix_function=None,
            temperature=0.6,
            max_new_tokens=2048,
            top_p=0.9
        ):

        url = self.endpoint_url

        headers = {
            'Authorization': self.api_key
        }

        data = {
            "chat": {
                "messages": messages
            },
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        response = self.session.post(url, json=data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            return result
        else:
            raise Exception('Failed to access Endpoint')

