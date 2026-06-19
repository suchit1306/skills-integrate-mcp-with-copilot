"""Database access layer for activities, students, and registrations."""

import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "school.db"

INITIAL_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


class ActivityNotFoundError(Exception):
    pass


class AlreadySignedUpError(Exception):
    pass


class NotSignedUpError(Exception):
    pass


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)

    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS activity_registrations (
                activity_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (activity_id, student_id),
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            """
        )

        existing_count = connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        if existing_count > 0:
            return

        for name, details in INITIAL_ACTIVITIES.items():
            activity_cursor = connection.execute(
                """
                INSERT INTO activities (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    details["description"],
                    details["schedule"],
                    details["max_participants"],
                ),
            )
            activity_id = activity_cursor.lastrowid

            for email in details["participants"]:
                connection.execute(
                    "INSERT OR IGNORE INTO students (email) VALUES (?)",
                    (email,),
                )
                student_id = connection.execute(
                    "SELECT id FROM students WHERE email = ?",
                    (email,),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT OR IGNORE INTO activity_registrations (activity_id, student_id)
                    VALUES (?, ?)
                    """,
                    (activity_id, student_id),
                )


def get_activities() -> dict:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT a.name, a.description, a.schedule, a.max_participants, s.email
            FROM activities a
            LEFT JOIN activity_registrations ar ON ar.activity_id = a.id
            LEFT JOIN students s ON s.id = ar.student_id
            ORDER BY a.name, s.email
            """
        ).fetchall()

    activities: dict[str, dict] = {}
    for row in rows:
        name = row["name"]
        if name not in activities:
            activities[name] = {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": [],
            }
        if row["email"]:
            activities[name]["participants"].append(row["email"])

    return activities


def _get_activity_id(connection: sqlite3.Connection, activity_name: str) -> int:
    activity = connection.execute(
        "SELECT id FROM activities WHERE name = ?",
        (activity_name,),
    ).fetchone()
    if activity is None:
        raise ActivityNotFoundError()
    return activity["id"]


def signup_for_activity(activity_name: str, email: str) -> None:
    with _connect() as connection:
        activity_id = _get_activity_id(connection, activity_name)

        connection.execute(
            "INSERT OR IGNORE INTO students (email) VALUES (?)",
            (email,),
        )
        student_id = connection.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()[0]

        existing_registration = connection.execute(
            """
            SELECT 1 FROM activity_registrations
            WHERE activity_id = ? AND student_id = ?
            """,
            (activity_id, student_id),
        ).fetchone()
        if existing_registration:
            raise AlreadySignedUpError()

        connection.execute(
            """
            INSERT INTO activity_registrations (activity_id, student_id)
            VALUES (?, ?)
            """,
            (activity_id, student_id),
        )


def unregister_from_activity(activity_name: str, email: str) -> None:
    with _connect() as connection:
        activity_id = _get_activity_id(connection, activity_name)

        student = connection.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        if student is None:
            raise NotSignedUpError()

        deleted = connection.execute(
            """
            DELETE FROM activity_registrations
            WHERE activity_id = ? AND student_id = ?
            """,
            (activity_id, student["id"]),
        )
        if deleted.rowcount == 0:
            raise NotSignedUpError()
