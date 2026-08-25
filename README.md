# Obsidian Vault Search MCP

> 🌐 **Languages**: [English](README_EN.md) | **中文**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/Zero_Deployments-Standard_Library-green" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT License">
</p>

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

```bash
cp .env.example .env
```

**最小可用** —— 只需 `VAULT_PATH`：

```ini
VAULT_PATH=/absolute/path/to/your/vault
VAULT_NAME=MyVault
```

**开启 LLM 功能**：

```ini
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
LLM_API_KEY=***
LLM_MODEL=glm-4-flash
```

---

## 使用

```bash
# 搜索笔记
python vault_search.py search "AI 编程技巧"

# 归纳相关笔记
python vault_search.py aggregate "机器学习最佳实践"
```

---

## Roadmap（能力成熟度路线）

本项目按「能力成熟度」分阶段演进，每一阶段在前一阶段之上叠加能力，越往后越强大、也越重运维。

| 阶段 | 组成 | 能力 | 状态 |
|------|------|------|------|
| 基础 | A 插件即时找 + D Bases 结构化 | 文件名/属性/全文的确定性查找，零配置、丝滑即时 | ✅ 已有（Obsidian 内） |
| 进阶 | + B agent/MCP 管检 | 按意思语义召回 + 多笔记归纳汇总 + 跨客户端 | ✅ 本项目 v1.0.0 |
| 高阶 | + C GraphRAG 图谱推理 | 实体/关系图谱、多跳推理、跨笔记因果链 | ⬜ 计划中（按阈值触发） |

### 当前位置
- 已从「基础」走到「进阶」：确定性查找（A+D）作 Obsidian 内即时兜底，语义检索与汇总（B，即本仓库）作主力。
- 路线图里**唯一尚未实现的段落是 C（高阶）**；A、D、B 均已落地。

### 各阶段适用场景
- **基础（A+D）**：笔记量中等、靠标题/标签/属性即可覆盖；追求零配置、Obsidian 内即时查找；不需要跨工具/汇总/对话。
- **进阶（A+D+B）**：笔记量大、只记得意思不记得标题高频；已在用 agent 客户端想对话式找笔记并接着用；有「找多篇 + 汇总/综述」需求；在意隐私不想上传全量笔记。
- **高阶（C）**：vault 达数万篇，且高频需要「多跳推理」（概念关系网、人物/事件溯源、跨笔记因果链）。

### 升级阈值（何时该上 C）
C 不是「进阶之后必做」，而是**按需求触发**：
- 触发条件：vault 规模到**数万篇** + 检索需求从「找单篇」升级为「搞清楚关系/来龙去脉/多跳因果」。
- 未达阈值时，上 C 属于提前透支复杂度（需建实体/关系图谱，构建与运维成本显著高于收益），**不建议**。
- 当前建议：把 B 用熟、把 A+D 当兜底；等被「关系推理」真正卡住时，再单独评估 C。

### 近期（非 C）待办
- [ ] 开放索引范围配置（当前已支持任意 `VAULT_PATH`；可继续扩大入库文件夹）。
- [ ] 提供 embedding 语义召回作为 LLM 重排之外的另一条语义路径（可选）。
- [ ] 多 vault / 多根目录统一索引。

---

## 安全

- **无硬编码凭证**：所有 API Key 存储在 `.env` 中
- **本地优先**：索引存储在 SQLite，不发送到云端
- **隐私保护**：无需 LLM 即可完全离线工作

详见 [SECURITY.md](SECURITY.md)。

---

## License

MIT

---

## English

> Find notes by meaning, not just keywords: search through thousands of Obsidian notes using natural language.

### Features

- **Semantic Search**: Chinese bigram tokenization + BM25 ranking
- **Local-First & Private**: All indexes stored locally in SQLite
- **Incremental Indexing**: Auto-updates based on file modification time
- **LLM Summarization (Optional)**: Aggregate related notes with AI
- **Multi-Provider Support**: OpenAI / DeepSeek / Qwen / GLM
- **Zero Dependencies**: Pure Python standard library

### Installation

```bash
git clone https://github.com/johnadams-bot/obsidian-vault-search-mcp.git
cd obsidian-vault-search-mcp
```

No `pip install` needed.

### License

MIT
