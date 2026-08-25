#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_search.py — 命令行入口（Obsidian 笔记语义检索，零安装）

子命令：
  index                 构建/增量更新索引
  search  "查询词"       本地 BM25 召回候选（文本）
  search  "查询词" --json  输出 JSON（便于脚本/MCP 调用）
  aggregate "查询词"      命中多篇关联笔记时，调用 LLM 做归纳汇总
  stats                 索引统计

配置（优先级：命令行 > 环境变量 > .env > config.json）：
  --vault PATH          待检索目录根（必填，或设 VAULT_PATH）
  --vault-name NAME     Obsidian 库名（用于 obsidian:// 链接，选填）
  --db PATH             索引库路径（选填）
  --top N               返回条数（默认 10）
LLM 相关见 config.example.json / .env.example。未配置 LLM 时仍可正常检索，
仅 aggregate 功能不可用（会提示配置）。
"""

import os
import sys
import argparse
from config import get, get_int, is_vault_configured
import vault_search_core as core


def _resolve_vault(args):
    vault = args.vault or get("VAULT_PATH")
    if not vault:
        sys.stderr.write(
            "错误：未指定知识库路径。请通过 --vault /path/to/vault 指定，\n"
            "或在 config.json / .env 中设置 VAULT_PATH。\n"
        )
        sys.exit(2)
    if not os.path.isdir(vault):
        sys.stderr.write("错误：目录不存在：%s\n" % vault)
        sys.exit(2)
    return vault


def _resolve_db(args):
    db = args.db or get("INDEX_DB")
    if db:
        return db
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_index.db")


def _print_results(results):
    if not results:
        print("未找到候选笔记。")
        return
    for i, n in enumerate(results, 1):
        print("%2d. [%s] %s" % (i, n["score"], n["title"]))
        print("     %s" % n["rel"])
        if n.get("uri"):
            print("     %s" % n["uri"])
        if n["summary"]:
            print("     总结: %s" % n["summary"][:120])
        print()


def main():
    ap = argparse.ArgumentParser(description="Obsidian 笔记本地语义检索（零安装）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="构建/增量更新索引")
    p_idx.add_argument("--vault")
    p_idx.add_argument("--vault-name", dest="vault_name")
    p_idx.add_argument("--db")
    p_idx.add_argument("--full", action="store_true", help="强制全量重建")

    p_sch = sub.add_parser("search", help="检索笔记")
    p_sch.add_argument("query")
    p_sch.add_argument("--vault")
    p_sch.add_argument("--vault-name", dest="vault_name")
    p_sch.add_argument("--db")
    p_sch.add_argument("--top", type=int, default=get_int("TOP_K", 10))
    p_sch.add_argument("--json", action="store_true")

    p_ag = sub.add_parser("aggregate", help="归纳汇总命中笔记")
    p_ag.add_argument("query")
    p_ag.add_argument("--vault")
    p_ag.add_argument("--vault-name", dest="vault_name")
    p_ag.add_argument("--db")
    p_ag.add_argument("--top", type=int, default=get_int("TOP_K", 10))

    p_st = sub.add_parser("stats", help="索引统计")
    p_st.add_argument("--vault")
    p_st.add_argument("--vault-name", dest="vault_name")
    p_st.add_argument("--db")

    args = ap.parse_args()
    vault_name = args.vault_name or get("VAULT_NAME", "")

    if args.cmd == "index":
        vault = _resolve_vault(args)
        db = _resolve_db(args)
        total, changed, removed = core.build_index(vault, db, full=args.full)
        print("索引完成：共 %d 篇（本次变更 %d，移除 %d）→ %s" % (total, changed, removed, db))

    elif args.cmd == "search":
        vault = _resolve_vault(args)
        db = _resolve_db(args)
        rerank = get("ENABLE_RERANK", "false").lower() == "true"
        try:
            results = core.search(args.query, db, vault, vault_name, args.top, rerank=rerank)
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(1)
        if args.json:
            print(core.json.dumps(results, ensure_ascii=False, indent=2))
        else:
            _print_results(results)

    elif args.cmd == "aggregate":
        vault = _resolve_vault(args)
        db = _resolve_db(args)
        try:
            results = core.search(args.query, db, vault, vault_name, args.top)
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(1)
        if not results:
            print("未找到相关笔记，无法汇总。")
            return
        from llm import is_configured, aggregate
        if not is_configured():
            print("LLM 未配置，无法做归纳汇总。以下是命中笔记（请配置 LLM 后重试）：\n")
            _print_results(results)
            print("配置方式见 .env.example / config.example.json（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL）。")
            return
        summary = aggregate(args.query, results)
        print("=== 归纳汇总（%d 篇相关笔记）===\n" % len(results))
        print(summary)
        print("\n=== 来源笔记 ===")
        for i, n in enumerate(results, 1):
            print("%d. %s  (%s)" % (i, n["title"], n.get("uri") or n["rel"]))

    elif args.cmd == "stats":
        vault = _resolve_vault(args)
        db = _resolve_db(args)
        try:
            core.ensure_fresh(vault, db)
        except FileNotFoundError:
            print("索引不存在，请先运行 index")
            return
        notes = core.load_notes(db)
        cats = {}
        for n in notes:
            cats[n["category"]] = cats.get(n["category"], 0) + 1
        print("索引库: %s" % db)
        print("笔记数: %d" % len(notes))
        print("分类分布:")
        for k, v in sorted(cats.items(), key=lambda x: -x[1]):
            print("  %4d  %s" % (v, k or "(无)"))


if __name__ == "__main__":
    main()
