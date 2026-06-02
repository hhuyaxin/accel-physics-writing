#!/usr/bin/env python3
"""
index_corpus.py —— 把 private_corpus/books/ 下的 PDF 建成本地向量索引(保留真实页码)。

链路(见 CLAUDE.md §7.5):
  pdfplumber 逐页读取(保留 page_number,这是"第 X 页"的唯一可信来源,不来自模型记忆)
    → 页内滑窗切块(每块带其页码)
    → 本地 sentence-transformers 模型编码(归一化)
    → faiss 建索引,连同分块元数据写入 private_corpus/index/(已 gitignore)

注意:page_number 是 PDF 物理页序(1 基)。若书有前言偏移,印刷页码可能与之相差固定值,
后续可加 --page-offset 修正;MVP 先用 PDF 页序并在引用时说明。
"""
from __future__ import annotations
import sys, json, pickle, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _config as C  # noqa: E402

# 字母 + 汉字;用"实际文字量"而非总字符数过滤,避免纯标点/公式/图页的垃圾块
_LETTERS = re.compile(r"[A-Za-z一-鿿]")
MIN_LETTERS = 20  # 一个块至少要有这么多字母/汉字才算有内容


def _letters(s: str) -> int:
    return len(_LETTERS.findall(s))


def iter_page_chunks(pdf_path: Path, win: int = 600, overlap: int = 150):
    """逐页抽文字,页内按字符滑窗切块;每块绑定其页码。
    跳过文字量过少的块(纯图/公式/标点页),否则会与无关查询产生虚高相似度(假阳)。"""
    import pdfplumber
    book = pdf_path.name
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw = page.extract_text() or ""
            t = " ".join(raw.split())  # 压平空白
            if _letters(t) < MIN_LETTERS:   # 跳过空白/纯图/纯公式页
                continue
            page_no = page.page_number  # 1 基 PDF 页
            chunks = [t] if len(t) <= win else \
                [t[i:i + win] for i in range(0, len(t), win - overlap)]
            for ch in chunks:
                if _letters(ch) >= MIN_LETTERS:   # 逐块再过滤,丢掉尾部碎块
                    yield {"book": book, "page": page_no, "text": ch}


def main():
    books = sorted(C.books_dir().glob("*.pdf"))
    if not books:
        sys.exit(f"未发现 PDF。请把书放入 {C.books_dir()}")

    print(f"待索引 {len(books)} 本:")
    for b in books:
        print(f"  - {b.name}")

    model = C.load_model()

    chunks: list[dict] = []
    for b in books:
        before = len(chunks)
        for ch in iter_page_chunks(b):
            chunks.append(ch)
        print(f"  ✓ {b.name}: {len(chunks) - before} 块")

    if not chunks:
        sys.exit("❌ 未抽到任何文本(可能是扫描版纯图 PDF,需 OCR,本 MVP 暂不支持)。")

    texts = [c["text"] for c in chunks]
    print(f"共 {len(texts)} 块,本地编码中(CPU,稍候)...")
    import numpy as np
    embs = model.encode(texts, batch_size=64, show_progress_bar=True,
                        normalize_embeddings=True)
    embs = np.asarray(embs, dtype="float32")

    import faiss
    index = faiss.IndexFlatIP(embs.shape[1])  # 归一化向量 + 内积 = 余弦
    index.add(embs)

    out = C.index_dir()
    out.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out / "corpus.faiss"))
    with open(out / "chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)
    json.dump(
        {"model": C.EMBEDDING_MODEL, "dim": int(embs.shape[1]),
         "n_chunks": len(chunks), "books": [b.name for b in books]},
        open(out / "meta.json", "w"), ensure_ascii=False, indent=2,
    )
    print(f"✅ 索引完成 → {out}")
    print(f"   {len(chunks)} 块 / {len(books)} 本 / 维度 {embs.shape[1]}")

    refresh_book_meta(books)


def refresh_book_meta(books):
    """生成/刷新 book_meta.yaml:为新书写入自动清洗的标题占位,保留已有的人工精修。"""
    try:
        import yaml
    except Exception:
        print("  (未装 pyyaml,跳过 book_meta 生成;书名将用自动清洗版)")
        return
    p = C.book_meta_path()
    existing = C.load_book_meta()
    changed = False
    for b in books:
        if b.name not in existing:
            existing[b.name] = {"title": C.clean_filename(b.name),
                                "authors": "", "edition": "", "cite": ""}
            changed = True
    if changed or not p.exists():
        header = ("# 书名美化映射:键=PDF 文件名。\n"
                  "# 引用优先用 cite(你填的规范名);cite 空则用 title(+authors,edition);\n"
                  "# 全空则自动清洗文件名。按需精修即可,重建索引不会覆盖你的修改。\n")
        p.write_text(header + yaml.safe_dump(existing, allow_unicode=True, sort_keys=True),
                     encoding="utf-8")
        print(f"  📒 已刷新书名映射 → {p}(可手工精修 cite/authors/edition)")


if __name__ == "__main__":
    main()
