import aiosql

chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, context, system, format, keep_alive, model_options) 
VALUES(:id, :name, :model, :context, :system, :format, :keep_alive, :model_options) RETURNING id;
-- name: save_context
UPDATE chat SET context = :context WHERE id = :id;
-- name: rename_chat
UPDATE chat SET name = :name WHERE id = :id;
-- name: edit_chat
UPDATE chat SET name = :name, system = :system, format = :format, keep_alive = :keep_alive, model_options = :model_options WHERE id = :id;
-- name: get_chats
SELECT id, name, model, context, system, format, keep_alive, model_options FROM chat;
-- name: get_chat
SELECT id, name, model, context, system, format, keep_alive, model_options FROM chat WHERE id = :id;
-- name: delete_chat
DELETE FROM chat WHERE id = :id;
-- name: save_message
INSERT INTO message(chat_id, author, text)
VALUES(:chat_id, :author, :text);
-- name: get_messages
SELECT author, text FROM message WHERE chat_id = :chat_id;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
