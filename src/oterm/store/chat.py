import aiosql

chat_sqlite = """
-- name: save_chat
INSERT OR REPLACE INTO chat(id, name, model, system, format, parameters, keep_alive, tools) 
VALUES(:id, :name, :model, :system, :format, :parameters, :keep_alive, :tools) RETURNING id;
-- name: rename_chat
UPDATE chat SET name = :name WHERE id = :id;
-- name: edit_chat
UPDATE chat SET name = :name, system = :system, format = :format, parameters = :parameters, keep_alive = :keep_alive, tools = :tools WHERE id = :id;
-- name: get_chats
SELECT id, name, model, system, format, parameters, keep_alive, tools FROM chat;
-- name: get_chat
SELECT id, name, model, system, format, parameters, keep_alive, tools FROM chat WHERE id = :id;
-- name: delete_chat
DELETE FROM chat WHERE id = :id;
-- name: save_message
INSERT OR REPLACE INTO message(id, chat_id, author, text) 
VALUES(:id, :chat_id, :author, :text) RETURNING id;
-- name: get_messages
SELECT id, author, text FROM message WHERE chat_id = :chat_id;
"""

queries = aiosql.from_str(chat_sqlite, "aiosqlite")
