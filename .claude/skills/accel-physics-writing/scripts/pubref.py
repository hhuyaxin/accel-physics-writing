#!/usr/bin/env python3
"""
pubref.py —— 降级链第 2 级 [开放获取·可访问] 的确定性查询。

对称于第 1 级的 retrieve.py:retrieve.py 查私有书给页码;pubref.py 查公开的
开放获取索引(references/public_reference_index.yaml)给**已核实的真实 DOI/链接**。

铁律:本脚本只输出 YAML 里**已联网核实**的条目;不命中就如实返回空 + 指向权威站点,
绝不编造 DOI。

用法:
  python pubref.py "space charge tune shift" [--json]
"""
from __future__ import annotations
import sys, json, argparse, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _config as C  # noqa: E402


def _index_path() -> Path:
    # 公开索引随 skill 走,锚定 skill 目录(无论装在哪都成立)
    return C.references_dir() / "public_reference_index.yaml"


def _load() -> dict:
    import yaml
    return yaml.safe_load(_index_path().read_text(encoding="utf-8")) or {}


# 无区分度的常见词:滤掉以免"beam/particle/accelerator"这类词造成假命中
STOP = {
    "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with", "is",
    "beam", "beams", "particle", "particles", "accelerator", "accelerators",
    "physics", "effect", "effects", "machine", "machines", "dynamics",
}


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", s.lower()) if t not in STOP and len(t) > 2}


def search(query: str) -> dict:
    data = _load()
    qt = _tokens(query)

    def score(item_topics, text):
        topic_toks = _tokens(" ".join(item_topics or []))
        text_toks = _tokens(text or "")
        return len(qt & topic_toks), len(qt & text_toks)

    papers = []
    for p in data.get("papers", []):
        topic_hits, title_hits = score(p.get("topics"), p.get("title", ""))
        # 论文必须至少命中一个**主题词**,避免仅标题撞词的假阳性
        if topic_hits > 0:
            papers.append((topic_hits * 2 + title_hits, p))
    papers.sort(key=lambda x: -x[0])

    venues = []
    for v in data.get("venues", []):
        th, xh = score(v.get("topics"), v.get("name", "") + " " + (v.get("note", "") or ""))
        s = th * 2 + xh
        if s > 0:
            venues.append((s, v))
    venues.sort(key=lambda x: -x[0])

    return {
        "papers": [p for _, p in papers[:5]],
        "venues": [v for _, v in venues[:4]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = search(a.query)

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if out["papers"]:
        print("已核实的开放获取文献(可直接引用 DOI):")
        for p in out["papers"]:
            cite = p.get("citation") or f"{p['authors']} ({p['year']})"
            print(f"  🔗 [开放获取·可访问] {p['title']} — {cite}")
            print(f"      DOI {p['doi']}  |  {p.get('url','')}  |  {p.get('license','')}")
    else:
        print("（公开索引中无已核实的对口文献)")

    if out["venues"]:
        print("\n相关权威站点(去站内检索关键词,勿凭记忆给具体 DOI):")
        for v in out["venues"]:
            print(f"  • {v['name']} — {v['url']}")

    if not out["papers"] and not out["venues"]:
        print("第 2 级无命中 → 继续降到第 3/4 级。")


if __name__ == "__main__":
    main()
