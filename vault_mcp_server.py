#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_mcp_server.py — Obsidian 笔记检索 MCP server（stdio，纯标准库，零安装）

暴露给任意支持 MCP 的客户端（WorkBuddy / Claude Desktop / Codex / Cline 等）的工具：
  - search_notes(query, top_k=10) : 语义召回候选（BM25 中文 bigram + 别名/标签/标题 boost），
                                     搜索前自动懒增量
  - aggregate_notes(query, top_k=5): 命中多篇关联笔记时，调用 LLM 做归纳汇总 + 来源列表
  - reindex(full=False)            : 增量/全量重建索引
  - stats()                        : 索引统计
  - read_note(path)                : 读取某篇笔记全文

配置方式（见 .env.example / config.example.json）：
  VAULT_PATH      必填，待检索目录根
  VAULT_NAME      选填，Obsidian 库名（生成 obsidian:// 链接）
  INDEX_DB        选填，索引库路径
  LLM_*           选填，配置后 aggregate_notes 与语义重排生效；不配置则仅本地 BM25 召回

首次调用 search_notes 时若索引不存在会自动建；之后每次搜索前自动补齐变更文件（懒增量）。
与 vault_search.py / CLI 共享同一套检索核心（vault_search_core.py），单一真相源。
"""

import os
import sys
import json
import argparse
from config import get, get_int, is_vault_configured, is_llm_configured
import vault_search_core as core


def _vault():
    vault = get("VAULT_PATH")
    if not vault:
        raise ValueError("未配置 VAULT_PATH：请在 config.json 或 .env 中设置知识库目录根路径。")
    return vault


def _vault_name():
    return get("VAULT_NAME", "")


def _db():
    db = get("INDEX_DB")
    if db:
        return db
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_index.db")


# ---------------- MCP 工具定义 ----------------
TOOLS = [
    {
        "name": "search_notes",
        "description": "在 Obsidian 笔记库中按自然语言语义检索笔记，返回带链接的候选列表。"
                       "适合'只记得大概内容/几个词'时找笔记。搜索前自动增量更新索引。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询，例如'用codex让多个ai智能体分工做自媒体'"},
                "top_k": {"type": "integer", "default": 10, "description": "返回候选数量"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "aggregate_notes",
        "description": "按查询检索多篇关联笔记，并调用（已配置的）LLM 做归纳汇总，返回合成摘要 + 来源列表。"
                       "未配置 LLM 时返回命中笔记清单并提示配置。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言查询"},
                "top_k": {"type": "integer", "default": 5, "description": "参与汇总的笔记数量"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "reindex",
        "description": "增量重建笔记索引（仅处理变更文件）。传 full=true 可强制全量重建。",
        "inputSchema": {
            "type": "object",
            "properties": {"full": {"type": "boolean", "default": False}},
            "required": []
        }
    },
    {
        "name": "stats",
        "description": "返回索引统计：笔记总数与分类分布。",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "read_note",
        "description": "读取指定笔记的全文内容（传入 path 或 rel 相对路径）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "笔记绝对路径或相对 vault 的路径"}
            },
            "required": ["path"]
        }
    },
]


def call_tool(name, args):
    vault = _vault()
    db = _db()
    vname = _vault_name()
    if name == "search_notes":
        q = args.get("query", "")
        top_k = int(args.get("top_k", 10))
        rerank = get("ENABLE_RERANK", "false").lower() == "true"
        try:
            core.ensure_fresh(vault, db)
            res = core.search(q, db, vault, vname, top_k, rerank=rerank)
        except Exception as e:
            return {"content": [{"type": "text", "text": "检索失败: %s" % e}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}], "isError": False}

    if name == "aggregate_notes":
        q = args.get("query", "")
        top_k = int(args.get("top_k", 5))
        try:
            core.ensure_fresh(vault, db)
            res = core.search(q, db, vault, vname, top_k)
        except Exception as e:
            return {"content": [{"type": "text", "text": "检索失败: %s" % e}], "isError": True}
        if not res:
            return {"content": [{"type": "text", "text": "未找到相关笔记，无法汇总。"}], "isError": False}
        from llm import is_configured, aggregate
        if not is_configured():
            text = ("LLM 未配置，无法归纳汇总。命中笔记如下（配置 LLM 后可自动汇总）：\n"
                    + json.dumps(res, ensure_ascii=False, indent=2)
                    + "\n\n配置方式见 .env.example / config.example.json（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL）。")
            return {"content": [{"type": "text", "text": text}], "isError": False}
        try:
            summary = aggregate(q, res)
        except Exception as e:
            return {"content": [{"type": "text", "text": "LLM 汇总失败: %s\n\n命中笔记：\n%s" % (e, json.dumps(res, ensure_ascii=False, indent=2))}], "isError": True}
        sources = "\n".join("%d. %s (%s)" % (i, n["title"], n.get("uri") or n["rel"]) for i, n in enumerate(res, 1))
        out = "=== 归纳汇总（基于 %d 篇相关笔记）===\n%s\n\n=== 来源笔记 ===\n%s" % (len(res), summary, sources)
        return {"content": [{"type": "text", "text": out}], "isError": False}

    if name == "reindex":
        try:
            total, changed, removed = core.build_index(vault, db, full=bool(args.get("full", False)))
        except Exception as e:
            return {"content": [{"type": "text", "text": "重建失败: %s" % e}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps({"total": total, "changed": changed, "removed": removed}, ensure_ascii=False)}], "isError": False}

    if name == "stats":
        try:
            core.ensure_fresh(vault, db)
        except Exception as e:
            return {"content": [{"type": "text", "text": "统计失败: %s" % e}], "isError": True}
        notes = core.load_notes(db)
        cats = {}
        for n in notes:
            cats[n["category"]] = cats.get(n["category"], 0) + 1
        return {"content": [{"type": "text", "text": json.dumps({"total": len(notes), "categories": cats}, ensure_ascii=False, indent=2)}], "isError": False}

    if name == "read_note":
        p = args.get("path", "")
        if not os.path.isabs(p):
            p = os.path.join(vault, p)
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            return {"content": [{"type": "text", "text": txt[:8000]}], "isError": False}
        except Exception as e:
            return {"content": [{"type": "text", "text": "读取失败: %s" % e}], "isError": True}

    return {"content": [{"type": "text", "text": "未知工具: %s" % name}], "isError": True}


def handle(req):
    method = req.get("method", "")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "obsidian-vault-search", "version": "1.0.0"}}}
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {})
        return {"jsonrpc": "2.0", "id": rid, "result": call_tool(name, args)}
    if method in ("resources/list", "prompts/list"):
        return {"jsonrpc": "2.0", "id": rid, "result": {method.split("/")[0]: []}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="")  # 不在此硬编码默认；以 config 为准
    ap.add_argument("--db", default="")
    args = ap.parse_args()

    # 允许命令行覆盖（命令行 > config）
    if args.vault:
        os.environ["VAULT_PATH"] = args.vault
    if args.db:
        os.environ["INDEX_DB"] = args.db

    if not is_vault_configured():
        sys.stderr.write(
            "[obsidian-vault-search] 警告：未检测到 VAULT_PATH。请在 config.json/.env 中配置，"
            "或在 mcp 启动命令后追加 --vault /path/to/vault。工具调用将返回配置错误。\n"
        )
    # 确保索引存在（配置就绪时）
    if is_vault_configured():
        try:
            core.ensure_fresh(_vault(), _db())
        except Exception as e:
            sys.stderr.write("[obsidian-vault-search] 初始索引失败: %s\n" % e)

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
