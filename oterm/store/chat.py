import aiosql


chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, context) 
VALUES(:id, :name, :model, :context) RETURNING id;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
