import aiosql


chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, context) 
VALUES(:id, :name, :model, :context) RETURNING id;
-- name: get_chats
SELECT id, name, model, context FROM chat;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
