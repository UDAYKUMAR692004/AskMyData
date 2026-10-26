"""Everything about the database lives here.

There are two databases:
  shop.db      -> the built-in sample data (sales + products)
  uploaded.db  -> data from the Excel/CSV file the user uploads
The app answers questions from whichever one is "active".
"""
import io
import os
import re
import sqlite3

DB_PATH = "shop.db"
UPLOAD_PATH = "uploaded.db"

use_uploaded = False  # becomes True after a file is uploaded

SAMPLE_SALES = [
    # (product, category, amount, sale_date)
    ("Laptop", "Electronics", 50000, "2026-01-05"),
    ("Phone", "Electronics", 20000, "2026-01-12"),
    ("Headphones", "Accessories", 3000, "2026-01-15"),
    ("Phone", "Electronics", 22000, "2026-02-02"),
    ("Keyboard", "Accessories", 1500, "2026-02-10"),
    ("Laptop", "Electronics", 52000, "2026-02-18"),
    ("Mouse", "Accessories", 800, "2026-02-20"),
    ("Tablet", "Electronics", 30000, "2026-03-03"),
    ("Headphones", "Accessories", 3200, "2026-03-09"),
    ("Phone", "Electronics", 21000, "2026-03-14"),
    ("Monitor", "Electronics", 12000, "2026-03-22"),
    ("Keyboard", "Accessories", 1700, "2026-04-01"),
    ("Laptop", "Electronics", 48000, "2026-04-06"),
    ("Mouse", "Accessories", 900, "2026-04-15"),
    ("Tablet", "Electronics", 29000, "2026-04-21"),
    ("Phone", "Electronics", 23000, "2026-05-02"),
    ("Monitor", "Electronics", 11500, "2026-05-11"),
    ("Headphones", "Accessories", 2800, "2026-05-19"),
    ("Laptop", "Electronics", 51000, "2026-05-28"),
    ("Mouse", "Accessories", 850, "2026-06-04"),
]

SAMPLE_PRODUCTS = [
    # (product, cost_price, supplier)
    ("Laptop", 38000, "TechSupply"),
    ("Phone", 15000, "MobileHub"),
    ("Headphones", 1800, "SoundCo"),
    ("Keyboard", 900, "SoundCo"),
    ("Mouse", 500, "TechSupply"),
    ("Tablet", 22000, "MobileHub"),
    ("Monitor", 8000, "TechSupply"),
]


def _active_path(sample=False):
    if sample or not use_uploaded:
        return DB_PATH
    return UPLOAD_PATH


def get_db(read_only=False, path=None):
    """Open a database. read_only=True means nothing can be changed."""
    path = path or DB_PATH
    if read_only:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return sqlite3.connect(path)


# ---------------------------------------------------------------- sample data
def setup():
    """Create the sample tables and fill them (only the first time)."""
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS sales (
               id INTEGER PRIMARY KEY,
               product TEXT,
               category TEXT,
               amount INTEGER,
               sale_date TEXT
           )"""
    )
    if db.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO sales (product, category, amount, sale_date) VALUES (?, ?, ?, ?)",
            SAMPLE_SALES,
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS products (product TEXT PRIMARY KEY, cost_price INTEGER, supplier TEXT)"
    )
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO products (product, cost_price, supplier) VALUES (?, ?, ?)",
            SAMPLE_PRODUCTS,
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------- reading
def run_query(sql, sample=False):
    """Run a SELECT query in read-only mode and return the rows."""
    db = get_db(read_only=True, path=_active_path(sample))
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def get_schema():
    """Describe the active tables to the AI: names, columns and 3 example rows.
    Built from the real database, so it works for any uploaded file."""
    db = get_db(read_only=True, path=_active_path())
    try:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        parts = []
        for table in tables:
            columns = db.execute(f'PRAGMA table_info("{table}")').fetchall()
            column_text = ", ".join(f"{c[1]} ({c[2] or 'text'})" for c in columns)
            examples = db.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchall()
            example_text = "\n".join("  " + str(row)[:200] for row in examples)
            parts.append(f"Table: {table}\nColumns: {column_text}\nExample rows:\n{example_text}")
        text = "\n\n".join(parts)
        if len(tables) > 1:
            text += "\n\nYou may JOIN tables using columns that have the same meaning."
        return text
    finally:
        db.close()


def describe_dataset():
    """Short summary of the active data, used by the web page."""
    db = get_db(read_only=True, path=_active_path())
    try:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = []
        for table in tables:
            cursor = db.execute(f'SELECT * FROM "{table}" LIMIT 5')
            names = [d[0] for d in cursor.description]
            preview = [dict(zip(names, row)) for row in cursor.fetchall()]
            count = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            result.append({"table": table, "columns": names, "rows": count, "preview": preview})
        return {"source": "uploaded" if use_uploaded else "sample", "tables": result}
    finally:
        db.close()


# ---------------------------------------------------------------- uploading
def _clean_name(text, prefix="t"):
    """Make a safe table/column name: lowercase letters, numbers and underscores."""
    name = re.sub(r"\W+", "_", str(text).strip().lower()).strip("_")
    if not name:
        name = prefix
    if name[0].isdigit():
        name = f"{prefix}_{name}"
    return name


def _clean_columns(columns):
    seen = {}
    result = []
    for column in columns:
        name = _clean_name(column, "col")
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        result.append(name)
    return result


def load_file(content, filename):
    """Read an uploaded .csv or .xlsx file and make it the active data."""
    global use_uploaded
    import pandas as pd

    lower = filename.lower()
    if lower.endswith(".csv"):
        try:
            frame = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            frame = pd.read_csv(io.BytesIO(content), encoding="latin-1")
        base = _clean_name(os.path.splitext(os.path.basename(filename))[0])
        frames = {base: frame}
    elif lower.endswith(".xlsx"):
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
        frames = {}
        for sheet_name, frame in sheets.items():
            name = _clean_name(sheet_name)
            while name in frames:
                name += "_x"
            frames[name] = frame
    else:
        raise ValueError("Please upload a .csv or .xlsx file")

    frames = {name: f for name, f in frames.items() if len(f) > 0 and len(f.columns) > 0}
    if not frames:
        raise ValueError("The file has no data in it")

    db = get_db(path=UPLOAD_PATH)
    try:
        # remove anything from a previous upload
        old = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in old:
            db.execute(f'DROP TABLE IF EXISTS "{table}"')
        for name, frame in frames.items():
            frame.columns = _clean_columns(frame.columns)
            frame.to_sql(name, db, if_exists="replace", index=False)
        db.commit()
    finally:
        db.close()

    use_uploaded = True
    return describe_dataset()


def use_sample_data():
    """Go back to the built-in sample data."""
    global use_uploaded
    use_uploaded = False
    return describe_dataset()
