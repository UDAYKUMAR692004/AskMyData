"""Checks how accurate the AI is.

For each test question we know the CORRECT SQL. We ask the AI for its SQL,
run both, and compare the rows. Run with:  python evaluate.py
"""
import ai
import database
from safety import clean_sql, is_safe_sql

TEST_CASES = [
    ("How many sales are there in total?",
     "SELECT COUNT(*) FROM sales"),
    ("What is the total sales amount?",
     "SELECT SUM(amount) FROM sales"),
    ("What is the most expensive single sale?",
     "SELECT MAX(amount) FROM sales"),
    ("How many Phone sales are there?",
     "SELECT COUNT(*) FROM sales WHERE product = 'Phone'"),
    ("What is the total amount for Laptop sales?",
     "SELECT SUM(amount) FROM sales WHERE product = 'Laptop'"),
    ("What is the total amount for the Accessories category?",
     "SELECT SUM(amount) FROM sales WHERE category = 'Accessories'"),
    ("Which product has the highest total sales amount?",
     "SELECT product FROM sales GROUP BY product ORDER BY SUM(amount) DESC LIMIT 1"),
    ("How many sales happened in March 2026?",
     "SELECT COUNT(*) FROM sales WHERE sale_date LIKE '2026-03%'"),
    ("What is the average amount of a Tablet sale?",
     "SELECT AVG(amount) FROM sales WHERE product = 'Tablet'"),
    ("List the different product names.",
     "SELECT DISTINCT product FROM sales"),
    ("How many Electronics sales are above 20000?",
     "SELECT COUNT(*) FROM sales WHERE category = 'Electronics' AND amount > 20000"),
    ("What was the date of the first sale?",
     "SELECT MIN(sale_date) FROM sales"),
]


def same_rows(a, b):
    return sorted(map(str, a)) == sorted(map(str, b))


def main():
    database.setup()
    schema = database.get_schema()
    correct = 0
    failures = []

    for question, correct_sql in TEST_CASES:
        expected = database.run_query(correct_sql)
        try:
            ai_sql = clean_sql(ai.question_to_sql(question, schema))
            safe, reason = is_safe_sql(ai_sql)
            if not safe:
                raise ValueError(f"unsafe: {reason}")
            got = database.run_query(ai_sql)
        except Exception as error:
            failures.append((question, f"ERROR: {error}", expected))
            continue

        if same_rows(got, expected):
            correct += 1
            print(f"PASS  {question}")
        else:
            failures.append((question, got, expected))
            print(f"FAIL  {question}")

    total = len(TEST_CASES)
    print(f"\nAccuracy: {correct}/{total} = {correct / total:.0%}")
    if failures:
        print("\nWrong answers (write about these in your README):")
        for question, got, expected in failures:
            print(f"- {question}\n    AI result: {got}\n    Expected:  {expected}")


if __name__ == "__main__":
    main()
