"""The API. Run with:  uvicorn main:app --reload"""
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

import ai
import database
from safety import clean_sql, is_safe_sql

app = FastAPI(title="AskMyData")

database.setup()


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

class Question(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "AskMyData is running"}


@app.get("/sales")
def all_sales():
    rows = database.run_query(
        "SELECT id, product, category, amount, sale_date FROM sales", sample=True
    )
    return [
        {"id": r[0], "product": r[1], "category": r[2], "amount": r[3], "sale_date": r[4]}
        for r in rows
    ]


@app.get("/dataset")
def dataset():
    """Which data is active right now, and what does it look like?"""
    return database.describe_dataset()


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Receive an Excel/CSV file and make it the data we answer questions from."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too big (limit is 5 MB)")
    try:
        info = database.load_file(content, file.filename or "")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Could not read the file: {error}")
    return {"message": "File loaded. You can now ask questions about it.", **info}


@app.post("/reset")
def reset():
    """Go back to the built-in sample data."""
    return database.use_sample_data()


@app.post("/ask")
def ask(body: Question):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please type a question")

    # Step 1: AI writes the SQL
    try:
        sql = clean_sql(ai.question_to_sql(question, database.get_schema()))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"AI service error: {error}")

    if sql == "CANNOT_ANSWER":
        return {"question": question, "sql": None, "rows": [],
                "answer": "Sorry, I can't answer that from the sales data."}

    # Step 2: safety check BEFORE running anything
    safe, reason = is_safe_sql(sql)
    if not safe:
        raise HTTPException(status_code=400, detail=f"Blocked unsafe query. {reason}")

    # Step 3: run the query (read-only)
    try:
        rows = database.run_query(sql)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"The AI wrote a broken query: {error}")

    # Step 4: AI explains the rows in plain English
    try:
        answer = ai.explain_result(question, sql, rows)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"AI service error: {error}")

    return {"question": question, "sql": sql, "rows": rows, "answer": answer}
