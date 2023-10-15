import aiosql


chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, context) 
VALUES(:id, :name, :model, :context) RETURNING id;
-- name: get_chats
SELECT id, name, model, context FROM chat;
-- name: delete_chat
DELETE FROM chat WHERE id = :id;
-- name: save_message
INSERT INTO message(chat_id, author, text)
VALUES(:chat_id, :author, :text);
-- name: get_messages
SELECT author, text FROM message WHERE chat_id = :chat_id;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
