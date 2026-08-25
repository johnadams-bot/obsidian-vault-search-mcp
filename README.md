<!-- readme-lang-toggle-start -->
<div align="right">
  <strong>🌐 Language:</strong>
  <button onclick="switchLang('zh')" id="btn-zh" style="background:#4a90e2;color:#fff;border:none;padding:4px 12px;margin:0 4px;border-radius:4px;cursor:pointer;">中文</button>
  <button onclick="switchLang('en')" id="btn-en" style="background:#eee;color:#333;border:1px solid #ccc;padding:4px 12px;margin:0 4px;border-radius:4px;cursor:pointer;">English</button>
</div>
<script>
function switchLang(lang) {
  document.getElementById('zh-content').style.display = lang === 'zh' ? 'block' : 'none';
  document.getElementById('en-content').style.display = lang === 'en' ? 'block' : 'none';
  document.getElementById('btn-zh').style.background = lang === 'zh' ? '#4a90e2' : '#eee';
  document.getElementById('btn-zh').style.color = lang === 'zh' ? '#fff' : '#333';
  document.getElementById('btn-en').style.background = lang === 'en' ? '#4a90e2' : '#eee';
  document.getElementById('btn-en').style.color = lang === 'en' ? '#fff' : '#333';
  localStorage.setItem('lang', lang);
}
(function() {
  const saved = localStorage.getItem('lang') || 'zh';
  switchLang(saved);
})();
</script>
<!-- readme-lang-toggle-end -->

<!-- zh-content-start -->
<div id="zh-content">

# Obsidian Vault Search MCP

> 用「自然语言」找笔记：只记得大概内容、几个关键词，也能从成千上万篇 Obsidian 笔记里精准找回。
> 纯 Python 标准库，**零安装、零外部依赖**，索引只存本地，可完全离线运行。

解决的核心痛点：Obsidian 自带的搜索是「精确匹配文件名/全文」，但人常常只记得笔记的**意思**、不记得准确标题。本项目用 BM25 + 中文 bigram 分词做本地召回，再由 LLM（可选）做语义重排与归纳汇总，实现「按意思找笔记」。

---

## 功能特性

- **按意思检索**：中文按字符 bigram 分词 + BM25 排序，标题/别名/标签加权，命中「只记得大概内容」的场景。
- **本地优先、隐私安全**：索引是本地 SQLite，不含任何外发；不配置 LLM 也能用。
- **增量索引**：按文件 mtime 自动增量更新，删除文件自动清理；MCP 调用时懒增量。
- **归纳汇总（aggregate）**：一次命中多篇关联笔记时，调用 LLM 合成一段总结并列出来源。
- **大模型可选可配**：支持 OpenAI / DeepSeek / 通义千问 / 智谱 GLM / 本地 llama.cpp 等任何 OpenAI 兼容端点；不配则降级为纯本地召回。
- **跨客户端通用**：作为标准 MCP server，可在 WorkBuddy、Claude Desktop、Codex、Cline 等任意支持 MCP 的客户端中使用。
- **零依赖**：仅用 Python 标准库，无需 `pip install`，不需要 API key 也能基础检索。

---

## 架构

```
  你的笔记 (.md)
      │  os.walk 扫描 + frontmatter/标题/别名/标签/总结/原文抽取
      ▼
  本地索引 (SQLite: vault_index.db)   ← 增量更新，仅存本地
      │  BM25 中文 bigram 召回 + 权重 boost
      ▼
  候选短名单  ──(可选 ENABLE_RERANK + LLM)──▶  语义重排
      │
      ▼
  MCP 工具 / CLI 输出（带 obsidian:// 或 file:// 链接）
      │
      ▼
  (可选) aggregate_notes ──▶ LLM 归纳汇总 + 来源列表
```

- **召回**永远在本地完成（BM25），快、隐私好、无费用。
- **语义层**（重排 / 汇总）是可选增强：配了 LLM 才有；没配也能正常检索。

---

## 安装

要求 Python 3.8+（仅用标准库，无需安装任何第三方包）。

```bash
git clone https://github.com/johnadams-bot/obsidian-vault-search-mcp.git
cd obsidian-vault-search-mcp
```

无需 `pip install`。

---

## 配置

优先复制示例文件再填写：

```bash
cp .env.example .env        # 或 cp config.example.json config.json
```

**最小可用（只检索，不汇总）** —— 只需 `VAULT_PATH`：

```ini
VAULT_PATH=/absolute/path/to/your/vault
VAULT_NAME=MyVault          # 可选，生成 obsidian:// 深链
```

**开启归纳汇总 / 语义重排** —— 追加 LLM 配置（任选一个兼容端点）：

```ini
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=***
LLM_MODEL=gpt-4o-mini

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=***
LLM_MODEL=deepseek-chat

# 通义千问 Qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=***
LLM_MODEL=qwen-plus

# 智谱 GLM
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
LLM_API_KEY=***
LLM_MODEL=glm-4-flash
```

---

## 使用

### CLI

```bash
# 搜索笔记
python vault_search.py search "AI 编程技巧"

# 归纳相关笔记
python vault_search.py aggregate "机器学习最佳实践"

# 重建索引
python vault_search.py index --force
```

### MCP Server

启动 MCP server 供 AI 客户端使用：

```bash
python vault_mcp_server.py
```

在 MCP 客户端（Claude Desktop、WorkBuddy 等）中配置：

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

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `VAULT_PATH` | 是 | Obsidian vault 绝对路径 |
| `VAULT_NAME` | 否 | vault 名称，用于 obsidian:// 深链 |
| `INDEX_DB` | 否 | 自定义索引数据库路径 |
| `TOP_K` | 否 | 返回结果数（默认 10） |
| `ENABLE_RERANK` | 否 | 启用 LLM 重排（true/false） |
| `LLM_BASE_URL` | 否 | LLM API 端点 |
| `LLM_API_KEY` | 否 | LLM API Key |
| `LLM_MODEL` | 否 | LLM 模型名称 |

---

## 安全

- **无硬编码凭证**：所有 API Key 存储在 `.env` 中
- **本地优先**：索引存储在 SQLite，不发送到云端
- **隐私保护**：无需 LLM 即可完全离线工作
- **零依赖**：无外部包需要审计

详见 [SECURITY.md](SECURITY.md)。

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)。

</div>
<!-- zh-content-end -->

<!-- en-content-start -->
<div id="en-content" style="display:none;">

# Obsidian Vault Search MCP

> Find notes by meaning, not just keywords: search through thousands of Obsidian notes using natural language.

A local-first, privacy-preserving MCP server for Obsidian vault search using BM25 retrieval with optional LLM reranking and summarization.

---

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
git clone https://github.com/johnadams-bot/obsidian-vault-search-mcp.git
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
LLM_API_KEY=***
LLM_MODEL=gpt-4o-mini

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=***
LLM_MODEL=deepseek-chat

# Qwen (Alibaba Cloud)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=***
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

</div>
<!-- en-content-end -->
