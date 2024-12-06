from dotenv import load_dotenv



class BaseLLM:
    """
    Interface for all LLM Endpoints. Custom Endpoints muss extend this class.
    """

    def __init__(self):
        load_dotenv()


    def test(self):
        messages = [
            {
                'role': 'user',
                'content': "What is the capital of france?"
            }
        ]
        answer = self.generate_text(messages)
        return answer

    def generate_text(
            self,
            messages,
            temperature=0.6,
            max_new_tokens=2048,
            top_p=0.9
    ) -> str | None:
        """
        Generates an answer to a chat.

        :param messages:
        :param temperature:
        :param max_new_tokens:
        :param top_p:
        :return:
        """
        pass
