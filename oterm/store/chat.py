import aiosql

chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, context, template, system, format) 
VALUES(:id, :name, :model, :context, :template, :system, :format) RETURNING id;
-- name: save_context
UPDATE chat SET context = :context WHERE id = :id;
-- name: rename_chat
UPDATE chat SET name = :name WHERE id = :id;
-- name: get_chats
SELECT id, name, model, context, template, system, format FROM chat;
-- name: get_chat
SELECT id, name, model, context, template, system, format FROM chat WHERE id = :id;
-- name: delete_chat
DELETE FROM chat WHERE id = :id;
-- name: save_message
INSERT INTO message(chat_id, author, text)
VALUES(:chat_id, :author, :text);
-- name: get_messages
SELECT author, text FROM message WHERE chat_id = :chat_id;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
