import sqlite3
import os
from datetime import datetime, timedelta

class Memory:
    def __init__(self, db_name="memory.db"):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_name)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Posts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                date TEXT,
                topic TEXT,
                content TEXT,
                image_path TEXT,
                was_approved BOOLEAN,
                posted_at TEXT,
                impressions INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                confidence_score INTEGER
            )
            ''')
            
            # Topics table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics_used (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                date_used TEXT,
                performance_score INTEGER DEFAULT 0
            )
            ''')
            
            # Voice log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_scores (
                id INTEGER PRIMARY KEY,
                date TEXT,
                authenticity_score INTEGER,
                buzzword_score INTEGER,
                overall_score INTEGER,
                flag_for_review BOOLEAN DEFAULT 0
            )
            ''')
            
            conn.commit()

    def save_post(self, topic: str, content: str, image_path: str, score: int, was_approved: bool = False):
        """Save a generated post to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute('''
            INSERT INTO posts (date, topic, content, image_path, confidence_score, was_approved)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (now, topic, content, image_path, score, was_approved))
            
            # Also log the topic as used
            cursor.execute('''
            INSERT INTO topics_used (topic, date_used)
            VALUES (?, ?)
            ''', (topic, now))
            
            conn.commit()

    def get_recent_topics(self, days: int = 7) -> list[str]:
        """Get topics used in the last N days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute("SELECT topic FROM topics_used WHERE date_used >= ?", (cutoff_date,))
            return [row[0] for row in cursor.fetchall() if row[0]]

    def save_voice_score(self, auth: int, buzz: int, overall: int):
        """Log voice scores to track drift."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            # Flag if overall score is below 65 (adjust threshold as needed)
            flagged = 1 if overall < 65 else 0
            
            cursor.execute('''
            INSERT INTO voice_scores (date, authenticity_score, buzzword_score, overall_score, flag_for_review)
            VALUES (?, ?, ?, ?, ?)
            ''', (now, auth, buzz, overall, flagged))
            
            conn.commit()

    def get_last_n_voice_scores(self, n: int = 10) -> list[int]:
        """Get the last N overall voice scores."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT overall_score FROM voice_scores ORDER BY date DESC LIMIT ?", (n,))
            return [row[0] for row in cursor.fetchall()]

    def check_voice_drift(self) -> bool:
        """Return True if average of last 10 scores drops below 65."""
        scores = self.get_last_n_voice_scores(10)
        if not scores:
            return False
        return (sum(scores) / len(scores)) < 65

    def get_post_history(self, limit: int = 10) -> list[dict]:
        """Get recent post history."""
        with self._get_connection() as conn:
            # Return dict-like objects
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM posts ORDER BY date DESC LIMIT ?", (limit,))
            # Convert to regular dicts for JSON serialization
            return [dict(row) for row in cursor.fetchall()]

    def mark_as_posted(self, post_id: int):
        """Mark an approved post as successfully posted to LinkedIn."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('UPDATE posts SET posted_at = ? WHERE id = ?', (now, post_id))
            conn.commit()
            
    def get_unposted_approved_drafts(self, limit: int = 5) -> list[dict]:
        """Fetch drafts that were approved by human but failed to post to API."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM posts 
            WHERE was_approved = 1 AND posted_at IS NULL 
            ORDER BY date DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_drafts_count(self) -> int:
        """Count how many approved drafts are waiting to be posted."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM posts WHERE was_approved = 1 AND posted_at IS NULL')
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_posts_today_count(self) -> int:
        """Count how many posts were successfully published today."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute('SELECT COUNT(*) FROM posts WHERE posted_at LIKE ?', (f"{today}%",))
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_last_post_id(self) -> int:
        """Get the ID of the most recently inserted post."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM posts ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()
            return row[0] if row else None

    def update_post_performance(self, post_id: int, impressions: int, likes: int, comments: int):
        """Update metrics for an existing post."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE posts 
            SET impressions = ?, likes = ?, comments = ?
            WHERE id = ?
            ''', (impressions, likes, comments, post_id))
            conn.commit()
