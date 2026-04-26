from sqlmodel import SQLModel, create_engine, Session

sqlite_file_name = "botanic.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def _ensure_news_incident_columns():
    """
    Lightweight sqlite migration for newly added NewsIncident fields.
    """
    import sqlite3

    conn = sqlite3.connect(sqlite_file_name)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(newsincident)")
        cols = {row[1] for row in cur.fetchall()}
        needed = {
            "street_name": "TEXT",
            "street_id": "TEXT",
            "lat": "REAL",
            "lng": "REAL",
        }
        for col, col_type in needed.items():
            if col not in cols:
                cur.execute(f"ALTER TABLE newsincident ADD COLUMN {col} {col_type}")
        conn.commit()
    finally:
        conn.close()

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _ensure_news_incident_columns()

def get_session():
    with Session(engine) as session:
        yield session
