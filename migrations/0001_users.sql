-- Users who may sign in (an invite is a row that has never logged in), their sessions, and their marks on jobs.
CREATE TABLE users (
  email TEXT PRIMARY KEY,
  name TEXT,
  role TEXT NOT NULL DEFAULT 'user',          -- 'admin' | 'user'
  invited_by TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_login TEXT
);

CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);

CREATE TABLE marks (
  email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
  job_id TEXT NOT NULL,
  status TEXT,                                -- 'saved' | 'applied' | 'hidden' | NULL
  opened_at TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (email, job_id)
);
