# Obsidian Vault Search MCP

> Find notes by meaning, not just keywords: search through thousands of Obsidian notes using natural language.

A local-first, privacy-preserving MCP server for Obsidian vault search using BM25 retrieval with optional LLM reranking and summarization.

## Core Features

- **Semantic Search**: Chinese bigram tokenization + BM25 ranking with title/alias/tags weighting
- **Local-First & Private**: All indexes stored locally in SQLite, no data sent externally
- **Incremental Indexing**: Auto-updates based on file modification time
- **LLM Summarization (Optional)**: Aggregate related notes with AI-powered summary generation
- **Multi-Provider Support**: OpenAI / DeepSeek / Qwen / GLM / local llama.cpp
- **Zero Dependencies**: Pure Python standard library, no pip install needed
- **Cross-Client Compatible**: Works with WorkBuddy, Claude Desktop, Codex, Cline, etc.

---

## Architecture

```
  Your Notes (.md)
      │  os.walk scan + frontmatter/title/alias/tags extraction
      ▼
  Local Index (SQLite: vault_index.db)  ← Incremental, local only
      │  BM25 Chinese bigram retrieval + weight boost
      ▼
  Candidate Results ──(optional ENABLE_RERANK + LLM)──▶  Rerank
      │
      ▼
  MCP Tools / CLI Output (with obsidian:// or file:// links)
      │
      ▼
  (Optional) aggregate_notes ──▶ LLM Summary + Source List
```

- **Retrieval** is always local (BM25) - fast, private, free
- **Semantic layer** (rerank/summarize) is optional: requires LLM config; works without it

---

## Installation

Requires Python 3.8+ (standard library only, no dependencies).

```bash
git clone https://github.com/<your-username>/obsidian-vault-search-mcp.git
cd obsidian-vault-search-mcp
```

No `pip install` needed.

---

## Configuration

Copy example files first:

```bash
cp .env.example .env        # or cp config.example.json config.json
```

**Minimal setup (search only, no summarization)** — only need `VAULT_PATH`:

```ini
VAULT_PATH=/absolute/path/to/your/vault
VAULT_NAME=MyVault          # Optional: for obsidian:// deep links
```

**Enable LLM summarization/reranking** — add LLM config (choose one):

```ini
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# Qwen (Alibaba Cloud)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-plus

# GLM (Zhipu AI)
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
LLM_API_KEY=***
LLM_MODEL=glm-4-flash
```

---

## Usage

### CLI

```bash
# Search notes
python vault_search.py search "AI programming techniques"

# Aggregate related notes with LLM summary
python vault_search.py aggregate "machine learning best practices"

# Rebuild index
python vault_search.py index --force
```

### MCP Server

Start the MCP server for use with AI clients:

```bash
python vault_mcp_server.py
```

Configure in your MCP client (Claude Desktop, WorkBuddy, etc.):

```json
{
  "mcpServers": {
    "obsidian-vault-search": {
      "command": "python",
      "args": ["/path/to/vault_mcp_server.py"]
    }
  }
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VAULT_PATH` | Yes | Absolute path to your Obsidian vault |
| `VAULT_NAME` | No | Vault name for obsidian:// links |
| `INDEX_DB` | No | Custom index database path |
| `TOP_K` | No | Number of results to return (default: 10) |
| `ENABLE_RERANK` | No | Enable LLM reranking (true/false) |
| `LLM_BASE_URL` | No | LLM API endpoint |
| `LLM_API_KEY` | No | LLM API key |
| `LLM_MODEL` | No | LLM model name |

---

## Security

- **No hardcoded credentials**: All API keys stored in `.env`
- **Local-first**: Index stored in SQLite, never sent to cloud
- **Privacy-preserving**: Works completely offline without LLM
- **Zero dependencies**: No external packages to audit

See [SECURITY.md](SECURITY.md) for details.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built with Python standard library (zero dependencies)
- Uses BM25 algorithm for information retrieval
- Supports OpenAI-compatible API endpoints
