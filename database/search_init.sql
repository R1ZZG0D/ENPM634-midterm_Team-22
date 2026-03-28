CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS challenge_flags (
    flag_key TEXT PRIMARY KEY,
    flag_value TEXT NOT NULL
);
