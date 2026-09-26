# RAG with haiku.rag

<video controls>
<source  src="../img/haiku-rag-demo.mp4" type="video/mp4">
</video>

[haiku.rag](https://github.com/ggozad/haiku.rag), also by `oterm`'s author, is a RAG library. It stores documents in LanceDB, searches them with hybrid (vector and full-text) search, and serves that search over MCP. Its default configuration runs the embedding model through Ollama.

## Build a database

The MCP server opens the database read-only, so documents go in through the `haiku-rag` command line:

```bash
uvx haiku-rag init --db /path/to/rag.lancedb
uvx haiku-rag add-src /path/to/report.pdf --db /path/to/rag.lancedb
uvx haiku-rag add-src https://example.com/article.html --db /path/to/rag.lancedb
uvx haiku-rag add-src /path/to/notes/ --db /path/to/rag.lancedb
```

A directory is added recursively. See the haiku.rag [command line reference](https://ggozad.github.io/haiku.rag/cli/) for everything else, including listing and deleting documents.

## Connect oterm

Add the server to `config.json` (run `oterm --data-dir` to find it):

```json
{
  "mcpServers": {
    "haiku-rag": {
      "command": "uvx",
      "args": ["haiku-rag", "mcp", "--stdio", "--db", "/path/to/rag.lancedb"]
    }
  }
}
```

Restart `oterm`, then select the `haiku-rag` tools when creating or editing a chat.

## Tools

| Tool | What it does |
| ---- | ------------ |
| `search_documents` | Hybrid search over the database. |
| `search_documents_by_image` | Search by image. Only offered with a multimodal embedder. |
| `list_documents` | Titles, URIs and metadata of the stored documents. |
| `get_document` | A whole document, in reading order. |
| `get_document_outline` | A document's heading tree, with page numbers. |
| `get_document_section` | The text of one section of a document. |
| `execute_code` | Runs a Python program in a sandbox over the selected documents. |

The model sees them as `haiku-rag_search_documents` and so on. The haiku.rag [MCP reference](https://ggozad.github.io/haiku.rag/mcp/) documents their arguments.

Then ask questions such as:

> What does the report say about revenue in the third quarter?

> Which of my notes mention the migration, and what did we decide?

## Configuration

haiku.rag reads `haiku.rag.yaml` from the path in `HAIKU_RAG_CONFIG_PATH`, then the current directory, then its own data directory. The MCP server runs in the directory `oterm` was started from, so either set `cwd` on the server or point it at the file:

```json
{
  "mcpServers": {
    "haiku-rag": {
      "command": "uvx",
      "args": ["haiku-rag", "mcp", "--stdio", "--db", "/path/to/rag.lancedb"],
      "env": {
        "HAIKU_RAG_CONFIG_PATH": "/path/to/haiku.rag.yaml"
      }
    }
  }
}
```

The embedding model in that configuration must match the one the database was built with. See the haiku.rag [configuration guide](https://ggozad.github.io/haiku.rag/configuration/) for providers, models and reranking.
