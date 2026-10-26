"""Run with:  python -m pytest"""
import os

import pytest
from fastapi.testclient import TestClient

import database
from safety import clean_sql, is_safe_sql

# Use separate test databases so we don't touch the real ones
database.DB_PATH = "test_shop.db"
database.UPLOAD_PATH = "test_uploaded.db"

import main  # noqa: E402  (must come after the paths are set)

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_db():
    for path in ("test_shop.db", "test_uploaded.db"):
        if os.path.exists(path):
            os.remove(path)
    database.use_uploaded = False
    database.setup()
    yield
    database.use_uploaded = False


# ---------- safety tests ----------
def test_select_is_allowed():
    assert is_safe_sql("SELECT * FROM sales")[0] is True


@pytest.mark.parametrize("bad", [
    "DROP TABLE sales",
    "DELETE FROM sales",
    "UPDATE sales SET amount = 0",
    "SELECT * FROM sales; DROP TABLE sales",
    "",
])
def test_dangerous_sql_is_blocked(bad):
    assert is_safe_sql(bad)[0] is False


def test_clean_sql_removes_code_fences():
    assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"


# ---------- API tests ----------
def test_home():
    assert client.get("/").json()["message"] == "AskMyData is running"


def test_sales_list():
    data = client.get("/sales").json()
    assert len(data) == len(database.SAMPLE_SALES)


def test_ask_works(monkeypatch):
    monkeypatch.setattr(main.ai, "question_to_sql", lambda q, s: "SELECT COUNT(*) FROM sales")
    monkeypatch.setattr(main.ai, "explain_result", lambda q, s, r: "There are 20 sales.")
    result = client.post("/ask", json={"question": "How many sales?"}).json()
    assert result["rows"] == [[20]]
    assert result["answer"] == "There are 20 sales."


def test_ask_blocks_unsafe_sql(monkeypatch):
    monkeypatch.setattr(main.ai, "question_to_sql", lambda q, s: "DROP TABLE sales")
    response = client.post("/ask", json={"question": "delete everything"})
    assert response.status_code == 400
    assert len(client.get("/sales").json()) == len(database.SAMPLE_SALES)  # data still there


def test_ask_empty_question():
    assert client.post("/ask", json={"question": "  "}).status_code == 400


def test_read_only_connection_cannot_write():
    with pytest.raises(Exception):
        database.run_query("DELETE FROM sales")


# ---------- upload tests ----------
def test_upload_csv_then_query():
    csv = b"Student Name,Marks\nAsha,90\nRavi,75\n"
    response = client.post("/upload", files={"file": ("My Students.csv", csv, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert "ask questions" in body["message"]
    assert body["tables"][0]["table"] == "my_students"
    assert body["tables"][0]["columns"] == ["student_name", "marks"]
    # the AI is now told about the new table, and queries run on it
    assert "my_students" in database.get_schema()
    assert database.run_query("SELECT COUNT(*) FROM my_students") == [(2,)]


def test_upload_wrong_file_type():
    response = client.post("/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_reset_goes_back_to_sample_data():
    client.post("/upload", files={"file": ("a.csv", b"x,y\n1,2\n", "text/csv")})
    assert client.get("/dataset").json()["source"] == "uploaded"
    client.post("/reset")
    assert client.get("/dataset").json()["source"] == "sample"
    assert "sales" in database.get_schema()
