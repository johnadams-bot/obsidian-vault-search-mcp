#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py — 可选的 LLM 接入层（OpenAI 兼容协议，纯标准库 urllib）

用途：
  - 命中多篇关联笔记时做「归纳汇总」（aggregate）
  - 启用 ENABLE_RERANK 时对 BM25 召回结果做语义重排（可选）

设计：零依赖。任何支持 OpenAI /chat/completions 协议的服务商都可直接用，
通过 config 的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 配置：
  OpenAI    : https://api.openai.com/v1
  DeepSeek  : https://api.deepseek.com/v1
  Qwen(通义): https://dashscope.aliyuncs.com/compatible-mode/v1
  GLM(智谱)  : https://open.bigmodel.cn/api/paas/v4
  本地 llama.cpp : http://127.0.0.1:8080/v1

未配置 LLM 时，调用方应自动降级为「纯本地 BM25 召回」，保证基础检索永远可用。
"""

import json
import urllib.request
from config import get, is_llm_configured


def is_configured():
    return is_llm_configured()


def chat(system_prompt, user_prompt, temperature=None, max_tokens=1200):
    """发起一次 OpenAI 兼容的 chat completion，返回文本。"""
    if not is_configured():
        raise RuntimeError(
            "LLM 未配置：请在 config.json 或 .env 设置 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL"
        )
    base = get("LLM_BASE_URL").rstrip("/")
    url = base + "/chat/completions"
    model = get("LLM_MODEL")
    try:
        temp = float(temperature if temperature is not None else get("LLM_TEMPERATURE", "0.3"))
    except (TypeError, ValueError):
        temp = 0.3

    payload = {
        "model": model,
        "temperature": temp,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + get("LLM_API_KEY"))
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8")
        obj = json.loads(body)
        return obj["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError("LLM HTTP 错误 %s: %s" % (e.code, detail))
    except Exception as e:
        raise RuntimeError("LLM 调用失败: %s" % e)


_SYSTEM_AGGREGATE = (
    "你是一个笔记归纳助手。下面提供了若干篇与用户问题相关的笔记片段"
    "（每篇含标题与正文摘录）。请围绕用户的问题，将这些片段归纳成一段"
    "条理清晰、可直接使用的总结，用简洁的中文回答；不要编造片段中没有的信息。"
    "最后用「参考笔记：」开头，按行列出你实际引用到的笔记标题。"
)


def aggregate(query, notes):
    """
    对多篇关联笔记做归纳汇总。

    :param query: 用户原始问题
    :param notes: 检索命中的笔记列表（每项含 title / summary / excerpt 等）
    :return: 合成摘要文本
    """
    if not notes:
        return "没有可供汇总的笔记。"
    parts = []
    for i, n in enumerate(notes, 1):
        title = n.get("title") or n.get("rel") or "未命名"
        text = (n.get("summary") or "") + "\n" + (n.get("excerpt") or "")
        text = text.strip()[:1500]
        parts.append("【笔记%d】%s\n%s" % (i, title, text))
    context = "\n\n".join(parts)
    user_prompt = "用户问题：%s\n\n相关笔记片段：\n%s" % (query, context)
    return chat(_SYSTEM_AGGREGATE, user_prompt, temperature=0.2, max_tokens=1200)


if __name__ == "__main__":
    if is_configured():
        print("LLM 已配置：provider=%s model=%s" % (get("LLM_PROVIDER"), get("LLM_MODEL")))
    else:
        print("LLM 未配置：将仅使用本地 BM25 召回。")
