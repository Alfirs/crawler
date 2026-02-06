from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import threading
from typing import Any
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class DbConfig:
    dialect: str
    database: str
    dsn: str | None
    placeholder: str


def parse_db_url(db_url: str) -> DbConfig:
    parsed = urlparse(db_url)
    scheme = parsed.scheme.lower()
    if scheme == "sqlite":
        if db_url.startswith("sqlite:///"):
            path = db_url[len("sqlite:///") :]
            path = unquote(path)
            path = path.lstrip("/")
        else:
            path = unquote(parsed.path)
        if not path:
            path = ":memory:"
        return DbConfig(dialect="sqlite", database=path, dsn=None, placeholder="?")

    if scheme in {"postgres", "postgresql"}:
        return DbConfig(dialect="postgres", database="", dsn=db_url, placeholder="%s")

    raise ValueError(f"Unsupported DB scheme: {scheme}")


class Database:
    def __init__(self, db_url: str) -> None:
        self._config = parse_db_url(db_url)
        self._conn: Any | None = None
        self._lock = threading.Lock()

    @property
    def dialect(self) -> str:
        return self._config.dialect

    @property
    def placeholder(self) -> str:
        return self._config.placeholder

    def connect(self) -> None:
        if self._conn is not None:
            return
        if self._config.dialect == "sqlite":
            conn = sqlite3.connect(self._config.database, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._conn = conn
            return

        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(self._config.dsn, row_factory=dict_row)

    def initialize(self) -> None:
        self.connect()
        if self._config.dialect == "sqlite":
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    current_node_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    pending_input_type TEXT,
                    last_prompt TEXT,
                    last_buttons TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                (),
            )
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    user_message TEXT,
                    bot_message TEXT,
                    chosen_action TEXT
                )
                """,
                (),
            )
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS tnved_codes (
                    code TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    duty_pct REAL DEFAULT 0.0,
                    vat_pct REAL DEFAULT 0.2,
                    excise TEXT,
                    gr31 TEXT,
                    licensing TEXT,
                    certification TEXT,
                    category TEXT,
                    extra TEXT
                )
                """,
                (),
            )
            return

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                user_id BIGINT PRIMARY KEY,
                current_node_id TEXT NOT NULL,
                data TEXT NOT NULL,
                pending_input_type TEXT,
                last_prompt TEXT,
                last_buttons TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            (),
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                timestamp TEXT NOT NULL,
                node_id TEXT NOT NULL,
                user_message TEXT,
                bot_message TEXT,
                chosen_action TEXT
            )
            """,
            (),
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS tnved_codes (
                code TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                duty_pct REAL DEFAULT 0.0,
                vat_pct REAL DEFAULT 0.2,
                excise TEXT,
                gr31 TEXT,
                licensing TEXT,
                certification TEXT,
                extra TEXT
            )
            """,
            (),
        )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            self._conn.commit()

    def execute_script(self, sql_script: str) -> None:
        """Executes a script of multiple SQL statements (SQLite only)."""
        self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        with self._lock:
            if self.dialect == "sqlite":
                 self._conn.executescript(sql_script)
            else:
                 # Poor man's script runner for PG
                 cur = self._conn.cursor()
                 cur.execute(sql_script)
            self._conn.commit()

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> None:
        self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        with self._lock:
            cur = self._conn.cursor()
            cur.executemany(sql, params)
            self._conn.commit()

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None:
        self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return list(cur.fetchall())
