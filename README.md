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

## 相对早期版本的四大改造

| # | 改造点 | 说明 |
|---|--------|------|
| ① | **知识库路径用户可配置** | 去掉硬编码的个人目录，改为 `VAULT_PATH`（命令行 / 环境变量 / `.env` / `config.json` 均可设），未设时给出清晰报错。 |
| ② | **大模型可选可配** | 新增 `llm.py`（OpenAI 兼容协议）。通过 `LLM_*` 配置选择服务商与模型；未配置时自动降级为纯 BM25 召回，检索永不失效。 |
| ③ | **增加归纳汇总功能** | 新增 `aggregate_notes` MCP 工具与 `aggregate` CLI 子命令：命中多篇关联笔记时调用 LLM 做归纳汇总，输出「合成摘要 + 来源笔记列表」。 |
| ④ | **去本地化、通用化、可公开** | 移除所有个人路径/账号等硬编码与敏感信息；提供标准 README / LICENSE(MIT) / .gitignore / .env.example / config.example.json，任何人 `git clone` 后即可使用。 |

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
git clone https://github.com/<your-username>/obsidian-vault-search-mcp.git
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
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# 通义千问 Qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-plus

# 智谱 GLM
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_API_KEY=xxx
LLM_MODEL=glm-4-flash

# 本地 llama.cpp（开启 --api 后）
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=sk-no-key-required
LLM_MODEL=local-model
```

> 配置优先级：**命令行 `--vault` > 环境变量 > `.env` > `config.json` > 默认值**。
> 密钥只从本地文件/环境变量读取，`.env` 与 `config.local.json` 已被 `.gitignore` 排除，请勿提交。

---

## 命令行用法

```bash
# 构建/增量更新索引
python3 vault_search.py index --vault /path/to/vault

# 检索（文本结果）
python3 vault_search.py search "用codex让多个ai智能体分工做自媒体" --top 10

# 检索（JSON，便于脚本调用）
python3 vault_search.py search "本地部署大模型 显存" --json --top 20

# 归纳汇总（需配置 LLM）
python3 vault_search.py aggregate "微信对话抽取工具" --top 5

# 索引统计
python3 vault_search.py stats --vault /path/to/vault
```

---

## 作为 MCP server 接入客户端

1. 参照 `mcp.example.json` 注册。以 WorkBuddy / Claude Desktop 为例，把下面内容写进对应 MCP 配置文件（路径替换为你的实际路径）：

```json
{
  "mcpServers": {
    "obsidian-vault-search": {
      "command": "python3",
      "args": ["/absolute/path/to/obsidian-vault-search-mcp/vault_mcp_server.py"],
      "env": {
        "VAULT_PATH": "/absolute/path/to/your/vault",
        "VAULT_NAME": "MyVault"
      }
    }
  }
}
```

2. 配置 LLM（可选，用于汇总/重排）：在 `.env` 或 `config.json` 中设置 `LLM_*`，或在上面的 `env` 里追加。

3. 重启客户端，工具 `search_notes` / `aggregate_notes` / `reindex` / `stats` / `read_note` 即生效。直接对它说「帮我找讲多智能体协作的笔记」「把这几篇微信工具相关的笔记汇总一下」即可。

### 可用工具

| 工具 | 作用 |
|------|------|
| `search_notes(query, top_k=10)` | 语义召回候选笔记（带链接） |
| `aggregate_notes(query, top_k=5)` | 召回 + LLM 归纳汇总 + 来源列表 |
| `reindex(full=false)` | 增量/全量重建索引 |
| `stats()` | 索引统计 |
| `read_note(path)` | 读取某篇笔记全文 |

---

## 文件结构

```
obsidian-vault-search-mcp/
├── config.py              # 配置加载（config.json/.env/env，优先级合并）
├── llm.py                 # 可选 LLM 接入（OpenAI 兼容，纯 stdlib）
├── vault_search_core.py   # 检索核心：索引 / BM25 / 可选重排
├── vault_search.py        # 命令行入口（index/search/aggregate/stats）
├── vault_mcp_server.py    # MCP server（stdio，5 个工具）
├── .env.example           # 配置模板（复制为 .env 填写）
├── config.example.json    # 配置模板（复制为 config.json 填写）
├── mcp.example.json       # MCP 客户端注册示例
├── LICENSE                # MIT
└── README.md
```

---

## 隐私与安全

- 索引仅包含笔记的标题、别名、标签、总结、原文摘录等**文本特征**，存于本地 SQLite，不会上传。
- 未配置 LLM 时，全程离线，无任何网络请求。
- LLM 仅在你主动配置且调用 `aggregate_notes` / 开启 `ENABLE_RERANK` 时，将「命中文档的摘要片段」发往你指定的端点。
- 密钥仅存于本地 `.env` / 环境变量，已被 `.gitignore` 排除。

---

## License

[MIT](./LICENSE)
