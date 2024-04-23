import aiosql

create_sqlite = """
-- name: create_chat_table
CREATE TABLE IF NOT EXISTS "chat" (
	"id"		INTEGER,
	"name"		TEXT,
	"model"		TEXT NOT NULL,
	"context"	TEXT NOT NULL,
	"system"	TEXT,
	"format"	TEXT,
	"keep_alive"	TEXT,
	"model_options"	TEXT NOT NULL DEFAULT '{}',
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- name: create_message_table
CREATE TABLE IF NOT EXISTS "message" (
	"chat_id"	INTEGER NOT NULL,
	"author"	TEXT NOT NULL,
	"text"		TEXT NOT NULL,
	FOREIGN KEY("chat_id") REFERENCES "chat"("id") ON DELETE CASCADE
);

-- name: get_user_version
PRAGMA user_version;

-- name: get_journal_mode
PRAGMA journal_mode;
"""

queries = aiosql.from_str(create_sqlite, "aiosqlite")
