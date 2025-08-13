# RAG with haiku.rag

<!-- ![Splash](img/haiku-rag-demo.gif) -->

<video controls>
<source  src="../img/haiku-rag-demo.mp4" type="video/mp4">
</video>

Transform oterm into a powerful RAG (Retrieval-Augmented Generation) system by integrating with [haiku.rag](https://github.com/ggozad/haiku.rag) (from the `oterm`'s author'), a SQLite-based RAG library that works seamlessly with oterm through MCP.

## What is haiku.rag?

haiku.rag is a comprehensive RAG library that:

- Uses only SQLite (no external vector databases needed)
- Supports 40+ file formats (PDF, DOCX, HTML, Markdown, code files, URLs)
- Provides hybrid search (semantic + full-text) with Reciprocal Rank Fusion
- Works with multiple embedding providers (Ollama, OpenAI, VoyageAI)
- Offers built-in reranking and question-answering capabilities
- Exposes functionality through MCP tools for seamless AI assistant integration

## Configuration

Add the haiku-rag MCP server to your oterm configuration. Edit your `config.json` file (run `oterm --data-dir` to find its location) and add:

```json
{
  "mcpServers": {
    "haiku-rag": {
      "command": "uvx",
      "args": [
        "haiku-rag",
        "serve",
        "--stdio",
        "--db",
        "/path/to/your/rag.db"
      ]
    }
  }
}
```

Replace `/path/to/your/rag.db` with the path where you want to store your RAG database.

## Available RAG Tools

Once configured, oterm will have access to powerful RAG capabilities through these MCP tools:

- **Add documents**: Upload text, files, or URLs to your knowledge base
- **List documents**: View all documents in your RAG database
- **Delete documents**: Remove documents from your knowledge base
- **Update documents**: Modify existing documents
- **Search documents**: Performs hybrid search on your knowledge base

## Usage Examples

### 1. Building a Personal Knowledge Base

Start a new chat in oterm and use the RAG tools to build your knowledge base:

> ```Add this document to my knowledge base: "Machine Learning is a subset of artificial intelligence that focuses on algorithms that can learn from data..."```

### 2. Adding Files

You can add various file types:

> ```Please add the PDF file at /Users/me/Documents/research_paper.pdf to my RAG database```

### 3. Adding Web Content

Add content from URLs:

> ```Add the content from https://example.com/article to my knowledge base```

### 4. Searching Your Knowledge Base

Perform semantic searches:

> ```Search my knowledge base for information about "neural networks"```

### 5. Question Answering

Ask questions about your documents:

> ```Based on my knowledge base, what are the main differences between supervised and unsupervised learning?```


## Advanced Configuration

### Custom Embedding Providers

Configure haiku.rag to use different embedding providers, rerankers, models by setting environment variables.
See `haiku.rag` [documentation](https://ggozad.github.io/haiku.rag/configuration/)

```json
{
  "mcpServers": {
    "haiku-rag": {
      "command": "uvx",
      "args": [
        "haiku-rag",
        "serve",
        "--stdio",
        "--db",
        "/path/to/rag.db"
      ],
      "env": {
        "EMBEDDINGS_PROVIDER": "ollama",
        "EMBEDDINGS_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

## Further Reading

- [haiku.rag Documentation](https://ggozad.github.io/haiku.rag/)
- [haiku.rag GitHub Repository](https://github.com/ggozad/haiku.rag)

## Example Use Cases

### Research Assistant
Build a personal research database by adding academic papers, articles, and notes. Ask questions across your entire research collection.

### Documentation Helper
Index your project's documentation, code comments, and README files. Get instant answers about your codebase.

### Learning Companion
Add course materials, textbooks, and learning resources. Create a personalized tutor that can answer questions about your study materials.
