#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_search_core.py — Obsidian 笔记本地检索核心（纯标准库，零安装）

算法（对应需求）：
  - 索引：扫描指定目录下所有 .md，抽取 frontmatter / 标题 / 别名 / 标签 / 总结 / 原文，
    存入本地 SQLite（vault_index.db）。按 mtime 增量更新，删除已移除文件。
  - 召回：BM25 + 中文按字符 bigram 分词，标题/别名/标签做精确 boost → 产出候选短名单。
  - 语义层（可选）：若配置了 LLM 且 ENABLE_RERANK=true，可对候选做语义重排；
    否则由调用方（MCP 客户端/智能体）自行做最终语义判断。

隐私：索引只存本地，不含任何外发；默认不读取 vault 以外的任何文件。
"""

import os
import re
import json
import time
import sqlite3
from urllib.parse import quote

K1 = 1.5
B = 0.75


# ---------------- 文本处理 ----------------
def tokenize(text):
    """中文按字符 bigram + ASCII 词；返回 term 列表。"""
    if not text:
        return []
    text = text.lower()
    tokens = []
    for m in re.findall(r"[a-z0-9]+", text):
        tokens.append(m)
    cjk = re.findall(r"[一-鿿]", text)
    for i in range(len(cjk) - 1):
        tokens.append("c:" + cjk[i] + cjk[i + 1])
    return tokens


def extract_frontmatter(text):
    """极简 frontmatter 解析，返回 (dict, body)。"""
    fm = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            body = text[end + 4:]
            lines = block.splitlines()
            key = None
            for ln in lines:
                m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", ln)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    if val.startswith("[") and val.endswith("]"):
                        val = [x.strip() for x in val[1:-1].split(",") if x.strip()]
                    fm[key] = val
                elif key and ln.strip().startswith("- "):
                    if isinstance(fm.get(key), list):
                        fm[key].append(ln.strip()[2:].strip())
    return fm, body


def section_between(body, head):
    """抽取 '## head' 与下一个 '## ' 之间的文本。"""
    pat = re.compile(r"##\s*" + re.escape(head) + r"\s*\n(.*?)(?=\n##\s|\Z)", re.S)
    m = pat.search(body)
    return m.group(1).strip() if m else ""


def build_record(path, vault_root):
    """从单个 .md 文件抽取一条记录。"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
    except Exception:
        return None
    fm, body = extract_frontmatter(raw)

    h1 = ""
    m = re.search(r"^#\s+(.+)$", body, re.M)
    if m:
        h1 = m.group(1).strip()
    title = h1 or (fm.get("title") if isinstance(fm.get("title"), str) else "") or os.path.splitext(os.path.basename(path))[0]

    aliases = fm.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    category = fm.get("category") if isinstance(fm.get("category"), str) else ""
    author = fm.get("author") if isinstance(fm.get("author"), str) else ""

    summary = section_between(body, "总结")
    if not summary and isinstance(fm.get("summary"), str):
        summary = fm["summary"]

    excerpt = section_between(body, "原文")
    if not excerpt:
        excerpt = body[:800]

    # 检索用 blob：加权拼接（标题/摘要权重 x2）
    blob = " ".join([
        title, title,
        " ".join(aliases),
        " ".join(tags),
        category, author,
        summary, summary,
        excerpt[:800],
    ])

    rel = os.path.relpath(path, vault_root)
    return {
        "path": path,
        "rel": rel,
        "title": title,
        "aliases": aliases,
        "tags": tags,
        "category": category,
        "author": author,
        "summary": summary[:600],
        "excerpt": excerpt[:400],
        "blob": blob,
        "mtime": int(os.path.getmtime(path)),
    }


def obsidian_uri(abspath, vault_name=""):
    """生成打开笔记的链接：配置了库名用 obsidian://，否则用 file://。"""
    if vault_name:
        return "obsidian://open?vault=%s&path=%s" % (quote(vault_name), quote(abspath))
    return "file://" + quote(abspath)


# ---------------- 索引（增量） ----------------
def ensure_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        path TEXT PRIMARY KEY, rel TEXT, title TEXT, aliases TEXT,
        tags TEXT, category TEXT, author TEXT, summary TEXT,
        excerpt TEXT, blob TEXT, mtime INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    conn.commit()
    return conn


def build_index(vault_root, db_path, full=False):
    """增量建索引：仅重算 mtime 变化的文件，删除已移除文件。full=True 强制全量。"""
    if not os.path.isdir(vault_root):
        raise NotADirectoryError("VAULT_PATH 不是有效目录: %s" % vault_root)
    conn = ensure_db(db_path)
    c = conn.cursor()
    if full:
        c.execute("DROP TABLE IF EXISTS notes")
        conn.commit()
        conn = ensure_db(db_path)
        c = conn.cursor()
    existing = {r[0]: r[1] for r in c.execute("SELECT path, mtime FROM notes").fetchall()}
    seen = set()
    changed = 0
    for root, _, files in os.walk(vault_root):
        for fn in files:
            if fn.lower().endswith(".md"):
                fp = os.path.join(root, fn)
                mt = int(os.path.getmtime(fp))
                seen.add(fp)
                if (not full) and fp in existing and existing[fp] == mt:
                    continue
                rec = build_record(fp, vault_root)
                if not rec:
                    continue
                c.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                    rec["path"], rec["rel"], rec["title"],
                    json.dumps(rec["aliases"], ensure_ascii=False),
                    json.dumps(rec["tags"], ensure_ascii=False),
                    rec["category"], rec["author"], rec["summary"],
                    rec["excerpt"], rec["blob"], rec["mtime"]))
                changed += 1
    removed = 0
    for fp in existing:
        if fp not in seen:
            c.execute("DELETE FROM notes WHERE path=?", (fp,))
            removed += 1
    c.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ('last_indexed', str(int(time.time()))))
    total = c.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    conn.commit()
    conn.close()
    return total, changed, removed


def ensure_fresh(vault_root, db_path):
    """懒增量：若 vault 内有文件比上次索引新，则补齐。返回 (total,changed,removed) 或 None。"""
    if not os.path.isdir(vault_root):
        raise NotADirectoryError("VAULT_PATH 不是有效目录: %s" % vault_root)
    conn = ensure_db(db_path)
    c = conn.cursor()
    row = c.execute("SELECT v FROM meta WHERE k='last_indexed'").fetchone()
    conn.close()
    last = float(row[0]) if row else 0.0
    newest = 0.0
    for root, _, files in os.walk(vault_root):
        for fn in files:
            if fn.lower().endswith(".md"):
                mt = os.path.getmtime(os.path.join(root, fn))
                if mt > newest:
                    newest = mt
    if newest > last or last == 0.0:
        return build_index(vault_root, db_path)
    return None


# ---------------- 检索 ----------------
def load_notes(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM notes").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bm25_search(notes, query, top_n=10):
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    docs = []
    for n in notes:
        toks = tokenize(n["blob"])
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        docs.append((n, tf, len(toks)))
    N = len(docs)
    df = {}
    for _, tf, _ in docs:
        for t in tf:
            df[t] = df.get(t, 0) + 1
    avgdl = sum(dl for _, _, dl in docs) / max(N, 1)
    idf = {}
    for t in set(q_tokens):
        idf[t] = (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5)

    q_lower = query.lower()
    results = []
    for n, tf, dl in docs:
        score = 0.0
        for t in q_tokens:
            if t in tf:
                f = tf[t]
                score += idf.get(t, 0) * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / max(avgdl, 1)))
        # 精确 boost
        if q_lower and q_lower in n["title"].lower():
            score += 5.0
        for al in n["aliases"]:
            if q_lower and q_lower in al.lower():
                score += 4.0
        for tg in n["tags"]:
            if q_lower and q_lower in tg.lower():
                score += 2.0
        if score > 0:
            results.append((score, n))
    results.sort(key=lambda x: x[0], reverse=True)
    return [(s, n) for s, n in results[:top_n]]


def search(query, db_path, vault_root, vault_name="", top_k=10, rerank=False):
    """
    执行检索：BM25 召回 →（可选）LLM 语义重排 → 组装带链接的结果。

    :param rerank: 仅当配置且 ENABLE_RERANK 时生效，否则忽略。
    :return: 结果列表，每项含 title/rel/path/uri/score/category/author/summary/excerpt
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError("索引不存在，请先运行 index / reindex")
    notes = load_notes(db_path)
    res = bm25_search(notes, query, max(top_k, 20))  # 先多召回，重排后再截断
    if rerank:
        try:
            from llm import chat
            res = _llm_rerank(query, res)
        except Exception:
            pass  # 重排失败不影响基础召回
    res = res[:top_k]
    out = []
    for score, n in res:
        out.append({
            "title": n["title"], "rel": n["rel"], "path": n["path"],
            "uri": obsidian_uri(n["path"], vault_name), "score": round(score, 3),
            "category": n["category"], "author": n["author"],
            "summary": n["summary"], "excerpt": n["excerpt"],
        })
    return out


def _llm_rerank(query, scored):
    """用 LLM 对候选做语义重排（基于相关性判断，返回重排后的 scored 列表）。"""
    from llm import chat
    items = []
    for i, (s, n) in enumerate(scored):
        items.append("%d. %s | %s" % (i, n["title"], (n["summary"] or n["excerpt"])[:200]))
    prompt = ("用户查询：%s\n\n候选笔记：\n%s\n\n请只返回一个 JSON 数组，"
              "元素为相关性从高到低的候选编号（如 [3,0,1,2]），不要解释。" % (query, "\n".join(items)))
    txt = chat("你是检索重排器，输出仅含 JSON 数组。", prompt, temperature=0.0, max_tokens=200)
    order = json.loads(re.search(r"\[.*\]", txt, re.S).group(0))
    ranked = []
    for idx in order:
        if 0 <= idx < len(scored):
            ranked.append(scored[idx])
    # 补齐未被选中的
    seen = set(order)
    for i, item in enumerate(scored):
        if i not in seen:
            ranked.append(item)
    return ranked
