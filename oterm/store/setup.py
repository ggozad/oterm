import aiosql

create_sqlite = """
-- name: create_chat_table
CREATE TABLE IF NOT EXISTS "chat" (
	"id"		INTEGER,
	"name"		TEXT,
	"model"		TEXT NOT NULL,
	"system"	TEXT,
	"format"	TEXT,
	"parameters"	TEXT,
    "keep_alive" INTEGER DEFAULT 5,
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
"""

queries = aiosql.from_str(create_sqlite, "aiosqlite")
