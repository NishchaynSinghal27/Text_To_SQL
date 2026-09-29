import os
import time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    max_retries=0,
)


def _call_with_retry(model_name, prompt, max_tokens, retries=3, json_mode=False):
    for attempt in range(retries):
        try:
            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except RateLimitError:
            if attempt == retries - 1:
                raise
            time.sleep(2)


class SQL_LLM:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        self.model_name = model_name

    def generate(self, prompt: str, max_new_tokens=300, json_mode=False) -> str:
        return _call_with_retry(self.model_name, prompt, max_new_tokens, json_mode=json_mode)


class ReasoningLLM:
    def __init__(self, model_name="llama-3.1-8b-instant"):
        self.model_name = model_name

    def generate(self, prompt: str, max_new_tokens=200, json_mode=False) -> str:
        return _call_with_retry(self.model_name, prompt, max_new_tokens, json_mode=json_mode)