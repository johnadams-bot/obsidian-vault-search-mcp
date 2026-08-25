#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — 配置加载（纯标准库，零安装）

配置来源与优先级（高 → 低）：
  1. 环境变量（environment variables）
  2. 项目根目录下的 .env / .env.local
  3. 项目根目录下的 config.json / config.local.json
  4. 内置默认值（全部为空，需用户填写）

config.json 与 .env 都从「脚本所在目录」和「当前工作目录」中查找。
所有敏感字段（LLM_API_KEY 等）只从本地文件/环境变量读取，绝不写死在代码里。
"""

import os
import json

# 脚本所在目录（用于定位 config.json / .env，避免受 CWD 影响）
_HERE = os.path.dirname(os.path.abspath(__file__))
_SEARCH_DIRS = [_HERE, os.getcwd()]

CONFIG_JSON_NAMES = ("config.json", "config.local.json")
ENV_NAMES = (".env", ".env.local")

# 支持的配置键与默认值。值含义见 .env.example / config.example.json
_DEFAULTS = {
    "VAULT_PATH": "",        # 必填：待检索的 Obsidian vault（或任意 .md 目录）根路径
    "VAULT_NAME": "",        # 选填：Obsidian 库名，用于生成 obsidian:// 链接；留空则用 file:// 链接
    "INDEX_DB": "",          # 选填：索引 SQLite 路径，留空则用脚本同目录 vault_index.db
    "TOP_K": "10",           # 检索默认返回条数
    "ENABLE_RERANK": "false",  # 选填：配置 LLM 后是否启用语义重排（true/false）
    # —— 以下为可选 LLM 配置（不填则仅使用本地 BM25 召回，不做汇总/重排）——
    "LLM_PROVIDER": "",      # 仅用于显示，如 openai / deepseek / qwen / glm / local
    "LLM_BASE_URL": "",      # OpenAI 兼容的 /v1 地址，如 https://api.openai.com/v1
    "LLM_API_KEY": "",       # 服务商 API Key（务必通过 .env 或环境变量提供，勿提交）
    "LLM_MODEL": "",         # 模型名，如 gpt-4o-mini / deepseek-chat / qwen-plus
    "LLM_TEMPERATURE": "0.3",
}


def _find_file(names):
    for d in _SEARCH_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _load_dotenv(path):
    """极简 .env 解析：支持 KEY=VALUE，值可带引号，跳过 # 注释与空行。"""
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
    except Exception:
        return {}
    return out


def _load_config():
    cfg = dict(_DEFAULTS)
    jp = _find_file(CONFIG_JSON_NAMES)
    if jp:
        for k, v in _load_json(jp).items():
            if k in _DEFAULTS and v not in (None, ""):
                cfg[k] = str(v)
    ep = _find_file(ENV_NAMES)
    if ep:
        for k, v in _load_dotenv(ep).items():
            if k in _DEFAULTS and v != "":
                cfg[k] = v
    for k in _DEFAULTS:
        if k in os.environ and os.environ[k] != "":
            cfg[k] = os.environ[k]
    return cfg


CONFIG = _load_config()


def get(key, default=None):
    """读取单个配置项。"""
    return CONFIG.get(key, default)


def get_int(key, default=0):
    try:
        return int(CONFIG.get(key, default))
    except (TypeError, ValueError):
        return default


def is_vault_configured():
    return bool(CONFIG.get("VAULT_PATH"))


def is_llm_configured():
    return bool(CONFIG.get("LLM_API_KEY")) and bool(CONFIG.get("LLM_BASE_URL")) and bool(CONFIG.get("LLM_MODEL"))


if __name__ == "__main__":
    print("当前生效配置（已隐藏密钥明文）：")
    for k, v in CONFIG.items():
        if "KEY" in k and v:
            v = v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
        print("  %-18s = %s" % (k, v))
