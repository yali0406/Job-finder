-- Marks on jobs (saved / applied / hidden, and when the job link was opened), shared between the
-- devices that use the same sync code. "space" is the SHA-256 of the code; the code itself is never stored.
CREATE TABLE IF NOT EXISTS sync_marks (
  space      TEXT NOT NULL,
  job_id     TEXT NOT NULL,
  status     TEXT,            -- NULL = cleared
  opened_at  TEXT,            -- NULL = not opened
  updated_at TEXT NOT NULL,   -- when the device made the change (last write wins)
  PRIMARY KEY (space, job_id)
);
