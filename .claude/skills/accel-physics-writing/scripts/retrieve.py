#!/usr/bin/env python3
"""
retrieve.py —— 按概念查询本地语料,返回 片段 + 真实页码 + 书名。

铁律(见 CLAUDE.md §7.5):
  - 只返回"片段 + 页码 + 出处",绝不返回整页正文。
  - 相似度不达阈值就返回空,触发 §4 降级链,而不是硬凑。
  - 页码来自 index_corpus.py 抽取的真实 PDF 页号,不来自模型记忆。

用法:
  python retrieve.py "空间电荷调谐移" [--k 5] [--threshold 0.35] [--json]
"""
from __future__ import annotations
import sys, json, pickle, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _config as C  # noqa: E402

SNIPPET_MAX = 300  # 返回片段最长字符数,避免大段复述正文


def load_index():
    import faiss
    idir = C.index_dir()
    fp = idir / "corpus.faiss"
    if not fp.exists():
        return None, None, None
    index = faiss.read_index(str(fp))
    chunks = pickle.load(open(idir / "chunks.pkl", "rb"))
    meta = json.load(open(idir / "meta.json"))
    return index, chunks, meta


def retrieve(query: str, k: int = 5, threshold: float = 0.5,
             page_offset: int = 0) -> dict:
    index, chunks, meta = load_index()
    if index is None:
        return {"status": "no_index", "results": []}
    import numpy as np
    model = C.load_model()
    q = np.asarray(model.encode([query], normalize_embeddings=True), dtype="float32")
    scores, idxs = index.search(q, min(k, len(chunks)))
    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or score < threshold:
            continue
        c = chunks[idx]
        snip = c["text"]
        if len(snip) > SNIPPET_MAX:
            snip = snip[:SNIPPET_MAX] + "…"
        pdf_page = int(c["page"])
        results.append({"book": c["book"],
                        "book_display": C.display_name(c["book"]),
                        "pdf_page": pdf_page,
                        "page": pdf_page + page_offset,  # 加偏移 = 印刷页码
                        "score": round(float(score), 3), "snippet": snip})
    return {"status": "ok" if results else "below_threshold",
            "page_offset": page_offset, "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--page-offset", type=int, default=0,
                    help="印刷页码 = PDF 页 + 此偏移;先翻看 PDF 某页对应的印刷页码算出,默认 0")
    ap.add_argument("--json", action="store_true", help="输出 JSON 供 skill 消费")
    a = ap.parse_args()
    out = retrieve(a.query, a.k, a.threshold, a.page_offset)

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if out["status"] == "no_index":
        print("⚠️ 尚无私有索引。请放书入 private_corpus/books/ 后运行 index_corpus.py。")
        print("   现在应降级到 §4 第 2/3/4 级(开放获取/网络/推断)。")
        return
    if not out["results"]:
        print("（未命中私有语料阈值 → 无 [私有参考·可验证] 命中,触发降级链)")
        return
    tag = "p." if a.page_offset else "PDF p."
    for r in out["results"]:
        print(f"[私有参考·可验证] {r['book_display']}  {tag}{r['page']}  (相似度 {r['score']})")
        print(f"   …{r['snippet']}…\n")
    if not a.page_offset:
        print("提示:以上为 PDF 物理页号(诚实标注)。若想精确到印刷页码,用 --page-offset 校准。")


if __name__ == "__main__":
    main()
