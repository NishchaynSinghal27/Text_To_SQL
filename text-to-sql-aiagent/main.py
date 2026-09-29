import os

from dotenv import load_dotenv
load_dotenv()

from pipeline.graph import build_graph
from langgraph.types import Command

app = build_graph()


def run_query(user_query: str, thread_id: str = "session-1"):
    config = {"configurable": {"thread_id": thread_id}}

    state = {
        "user_query": user_query,
        "db_url": os.getenv("CHINOOK_DB_URL"),
        "readonly_db_url": os.getenv("CHINOOK_READONLY_DB_URL"),
        "sql_attempts": 0,
        "max_iter": 3,
    }

    result = app.invoke(state, config=config)

    while "__interrupt__" in result:
        question = result["__interrupt__"][0].value["question"]
        print("\nClarification needed:", question)
        user_reply = input("Your answer: ")
        result = app.invoke(Command(resume=user_reply), config=config)

    print("\n--- Final Answer ---")
    print(result.get("final_answer"))
    print("\n--- SQL Used ---")
    print(result.get("generated_sql"))

    return result


import uuid

if __name__ == "__main__":
    query = input("Ask a question about the music store database: ")
    thread_id = str(uuid.uuid4())
    run_query(query, thread_id=thread_id)