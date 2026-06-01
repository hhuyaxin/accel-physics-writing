#!/usr/bin/env python3
"""
_config.py —— 检索链各脚本的单一真相源(模型名、路径、离线加载)。
被 index_corpus.py / retrieve.py / fetch_model.py(可选)共用,避免参数漂移。
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path

# 必须与 setup.sh 的 EMB_MODEL 一致;允许环境变量覆盖。
EMBEDDING_MODEL = os.environ.get(
    "EMB_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def project_root() -> Path:
    """从本文件向上找到项目根(含 private_corpus 或 CLAUDE.md 的目录)。"""
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "private_corpus").exists() or (anc / "CLAUDE.md").exists():
            return anc
    return here.parents[4]  # 兜底:scripts/ 上溯 4 层


def model_dir() -> Path:
    return project_root() / ".cache" / "st-models" / EMBEDDING_MODEL.split("/")[-1]


def books_dir() -> Path:
    return project_root() / "private_corpus" / "books"


def index_dir() -> Path:
    return project_root() / "private_corpus" / "index"


def load_model():
    """离线加载本地 embedding 模型;模型缺失给出清晰指引。"""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    md = model_dir()
    if not md.exists():
        sys.exit(f"❌ 模型目录不存在:{md}\n   请先运行 setup.sh 初始化环境。")
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(str(md))


# ---------------- 书名美化 ----------------
def book_meta_path() -> Path:
    """书目元数据映射(文件名→规范引用名),放私有目录,用户可手工精修。"""
    return project_root() / "private_corpus" / "book_meta.yaml"


def clean_filename(fn: str) -> str:
    """从下载文件名自动剥离 z-library 等水印,生成可读书名(自动兜底)。"""
    name = re.sub(r"\.(pdf|epub|djvu|mobi)$", "", fn, flags=re.I)
    # 去掉常见盗版/镜像站水印 token 及其 .sk 之类后缀
    name = re.sub(r"(z-?library|z-?lib|1lib|libgen|annas?-?archive)[^A-Za-z0-9]*\w*",
                  " ", name, flags=re.I)
    name = re.sub(r"\b\w*\.sk\b", " ", name)        # 残留的 *.sk
    name = re.sub(r"\([^A-Za-z]*\)", " ", name)     # 删空括号组,如 "( , , )"
    name = re.sub(r"[_\-]+", " ", name)             # 下划线/连字符 → 空格
    name = re.sub(r"\s*,\s*(?=,|\)|$)", "", name)   # 删多余逗号
    name = re.sub(r"\s+", " ", name).strip(" -_·,")
    return name or fn


def load_book_meta() -> dict:
    p = book_meta_path()
    if not p.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def display_name(fn: str) -> str:
    """返回用于引用的书名:优先用户在 book_meta.yaml 里填的 cite/title,否则自动清洗文件名。"""
    meta = load_book_meta().get(fn) or {}
    if meta.get("cite"):
        return str(meta["cite"])
    if meta.get("title"):
        bits = [str(meta["title"])]
        if meta.get("authors"):
            bits.append(f"({meta['authors']}" + (f", {meta['edition']})" if meta.get("edition") else ")"))
        return " ".join(bits)
    return clean_filename(fn)
