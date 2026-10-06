import json
import sqlite3
from datetime import datetime, timezone


DB_PATH = "event_agent.db"


def init_db():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS experiences (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                trigger TEXT NOT NULL,
                context TEXT NOT NULL,
                tool_calls TEXT NOT NULL,
                post_observation TEXT,
                outcome TEXT NOT NULL,
                final_result TEXT NOT NULL
            )
            """
        )

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(experiences)"
            )
        }

        if "execution" not in columns:
            connection.execute(
                "ALTER TABLE experiences ADD COLUMN execution TEXT"
            )


def save_experience(experience):
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO experiences (
                run_id,
                created_at,
                trigger,
                context,
                tool_calls,
                post_observation,
                outcome,
                execution,
                final_result
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experience["run_id"],
                created_at,
                json.dumps(experience["trigger"]),
                json.dumps(experience["context"]),
                json.dumps(experience["tool_calls"]),
                json.dumps(experience["post_observation"]),
                json.dumps(experience["outcome"]),
                json.dumps(experience["execution"]),
                experience["final_result"],
            ),
        )


def get_recent_experience(trigger_type):
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT
                run_id,
                created_at,
                trigger,
                context,
                tool_calls,
                post_observation,
                outcome,
                final_result,
                execution
            FROM experiences
            ORDER BY created_at DESC            
            """
        ).fetchall()

    for row in rows:
        trigger = json.loads(row[2])

        if trigger.get("type") != trigger_type:
            continue

        return {
            "run_id": row[0],
            "created_at": row[1],
            "trigger": trigger,
            "context": json.loads(row[3]),
            "tool_calls": json.loads(row[4]),
            "post_observation": (
                json.loads(row[5])
                if row[5] is not None
                else None
            ),
            "outcome": json.loads(row[6]),
            "final_result": row[7],
            "execution": (
                json.loads(row[8])
                if row[8] is not None
                else None
            ),
        }

    return None