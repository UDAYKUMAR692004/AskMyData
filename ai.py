"""All talking to the AI (Gemini) happens here."""
import os

from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY from the .env file

MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")


def _ask_ai(system, user, max_tokens=500):
    # Imported here so the tests can run without an API key
    from google import genai
    from google.genai import types

    client = genai.Client()  # finds GEMINI_API_KEY automatically
    response = client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


def question_to_sql(question, schema):
    """Step 1: turn the user's question into a SQL query."""
    system = (
        "You convert questions into SQLite SELECT queries.\n"
        f"{schema}\n"
        "Rules: reply with ONLY the SQL query, nothing else. "
        "Only use the table and columns above. Never write INSERT, UPDATE, DELETE or DROP. "
        "If the question cannot be answered from this table, reply with exactly: CANNOT_ANSWER"
    )
    return _ask_ai(system, question)


def explain_result(question, sql, rows):
    """Step 2: turn the database rows into a short, plain-English answer."""
    system = (
        "You explain database results in one or two simple sentences. "
        "Use ONLY the rows given. Do not invent numbers. "
        "If the rows are empty, say no data was found."
    )
    user = f"Question: {question}\nSQL used: {sql}\nRows: {rows}"
    return _ask_ai(system, user)