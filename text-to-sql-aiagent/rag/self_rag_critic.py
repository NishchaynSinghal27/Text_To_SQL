from pydantic import BaseModel
from pipeline.llm import ReasoningLLM

llm = ReasoningLLM()


class SchemaRelevance(BaseModel):
    relevant: bool


CRITIC_PROMPT = """You are checking if retrieved database schema info is enough to answer a question.

Question: {query}

Retrieved schema:
{schema_text}

Does this schema contain the tables/columns needed to answer the question?
Respond with only valid JSON matching this schema: {{"relevant": true or false}}
"""


class SelfRAGCritic:
    def __init__(self):
        self.llm = llm

    def check(self, query: str, chunks: list[dict]) -> bool:
        schema_text = "\n\n".join(c["text"] for c in chunks)
        prompt = CRITIC_PROMPT.format(query=query, schema_text=schema_text)

        response = self.llm.generate(prompt, max_new_tokens=500, json_mode=True)

        try:
            parsed = SchemaRelevance.model_validate_json(response)
            return parsed.relevant
        except Exception:
            # fail safe: don't get stuck looping forever on a bad response
            return True