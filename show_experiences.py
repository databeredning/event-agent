import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "event_agent.db"


def main():
    if not DB_PATH.exists():
        sys.exit(f"Database not found: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    try:
        rows = connection.execute(
            """
            SELECT run_id, created_at, trigger, context, outcome
            FROM experiences
            ORDER BY created_at
            """
        ).fetchall()
    except sqlite3.OperationalError as e:
        sys.exit(f"Query failed: {e}")
    finally:
        connection.close()

    for run_id, created_at, trigger, context, outcome in rows:
        print()
        print("RUN:", run_id)
        print("TIME:", created_at)
        print("TRIGGER:", trigger)
        print("CONTEXT:", context)
        print("OUTCOME:", outcome)


if __name__ == "__main__":
    main()
