import sqlite3
import os
from datetime import datetime, timedelta

# Schema initialized once per process — not on every Memory() instantiation
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory.db")
_INITIALIZED = False

def _ensure_schema():
    global _INITIALIZED
    if _INITIALIZED:
        return
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")   # faster concurrent reads
        conn.execute("PRAGMA synchronous=NORMAL")  # safe but faster than FULL
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS posts (
                id               INTEGER PRIMARY KEY,
                date             TEXT,
                topic            TEXT,
                content          TEXT,
                image_path       TEXT,
                was_approved     BOOLEAN,
                posted_at        TEXT,
                impressions      INTEGER DEFAULT 0,
                likes            INTEGER DEFAULT 0,
                comments         INTEGER DEFAULT 0,
                confidence_score INTEGER
            );
            CREATE TABLE IF NOT EXISTS topics_used (
                id                INTEGER PRIMARY KEY,
                topic             TEXT,
                date_used         TEXT,
                performance_score INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS voice_scores (
                id                 INTEGER PRIMARY KEY,
                date               TEXT,
                authenticity_score INTEGER,
                buzzword_score     INTEGER,
                overall_score      INTEGER,
                flag_for_review    BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_topics_date     ON topics_used(date_used);
            CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
            CREATE INDEX IF NOT EXISTS idx_posts_approved  ON posts(was_approved, posted_at);
            CREATE INDEX IF NOT EXISTS idx_voice_date      ON voice_scores(date);
        ''')
        conn.commit()
    _INITIALIZED = True


class Memory:
    def __init__(self, db_name="memory.db"):
        global _DB_PATH
        _DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_name)
        _ensure_schema()

    def _conn(self):
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def save_post(self, topic: str, content: str, image_path: str,
                  score: int, was_approved: bool = False) -> int:
        """Save post + topic in one transaction. Returns the new post id."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO posts (date,topic,content,image_path,confidence_score,was_approved) "
                "VALUES (?,?,?,?,?,?)",
                (now, topic, content, image_path, score, was_approved)
            )
            post_id = cur.lastrowid
            conn.execute(
                "INSERT INTO topics_used (topic,date_used) VALUES (?,?)",
                (topic, now)
            )
            conn.commit()
        return post_id

    def get_recent_topics(self, days: int = 7) -> list[str]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT topic FROM topics_used WHERE date_used >= ?", (cutoff,)
            ).fetchall()
        return [r["topic"] for r in rows if r["topic"]]

    def save_voice_score(self, auth: int, buzz: int, overall: int):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO voice_scores (date,authenticity_score,buzzword_score,overall_score,flag_for_review) "
                "VALUES (?,?,?,?,?)",
                (now, auth, buzz, overall, 1 if overall < 65 else 0)
            )
            conn.commit()

    def check_voice_drift(self) -> bool:
        """Single SQL AVG — no Python math needed."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT AVG(overall_score) FROM ("
                "  SELECT overall_score FROM voice_scores ORDER BY date DESC LIMIT 10"
                ")"
            ).fetchone()
        avg = row[0]
        return bool(avg is not None and avg < 65)

    def get_post_history(self, limit: int = 10) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM posts ORDER BY date DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_as_posted(self, post_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE posts SET posted_at=? WHERE id=?",
                (datetime.now().isoformat(), post_id)
            )
            conn.commit()

    def get_unposted_approved_drafts(self, limit: int = 5) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM posts WHERE was_approved=1 AND posted_at IS NULL "
                "ORDER BY date DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_drafts_count(self) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM posts WHERE was_approved=1 AND posted_at IS NULL"
            ).fetchone()[0]

    def get_posts_today_count(self) -> int:
        """Use DATE() — indexable, no LIKE scan."""
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM posts WHERE DATE(posted_at)=DATE('now')"
            ).fetchone()[0]

    def update_post_performance(self, post_id: int, impressions: int,
                                likes: int, comments: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE posts SET impressions=?,likes=?,comments=? WHERE id=?",
                (impressions, likes, comments, post_id)
            )
            conn.commit()
