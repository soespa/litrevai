from dotenv import load_dotenv


load_dotenv()

class BaseLLM:
    """
    Interface for all LLM Endpoints. Custom Endpoints muss extend this class.
    """

    def __init__(self):
        pass

    def generate_text(
        self,
        messages,
        prefix_function=None,
        temperature=0.6,
        max_new_tokens=2048,
        top_p=0.9
    ) -> str | None:
        pass


