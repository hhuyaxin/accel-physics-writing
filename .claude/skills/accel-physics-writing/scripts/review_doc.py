#!/usr/bin/env python3
"""
review_doc.py —— 整篇文档/讲稿物理审查(能力 C)。实现 CLAUDE.md §6 / document_review_checklist.md。

设计(混合):
  机械可算的部分由脚本做 —— 解析定位 + 单位/数量级 linter(高置信疑点,如发射度 5 m·rad);
  需判读的部分(违反定律 / 无出处断言 / 违反直觉)由脚本产出**结构化清单**,逼 AI 逐条按 §6 判,
  不许回"看起来不错"。

支持输入:.md / .txt / .tex(按行定位)、.pdf(按页定位,PPT 可先导出 PDF)。
依赖:仅 pdfplumber(已装),无新增。

用法:
  review_doc.py <文件>            # 审查真实文档
  review_doc.py --selftest        # 用植入错误的样例自测(展示能抓出量纲/数量级/单位混用)
"""
from __future__ import annotations
import argparse, re, sys, tempfile, os
from pathlib import Path

# ---------- 单位换算 ----------
LEN = {"pm": 1e-12, "nm": 1e-9, "um": 1e-6, "µm": 1e-6, "μm": 1e-6,
       "mm": 1e-3, "cm": 1e-2, "m": 1.0}
ANG = {"urad": 1e-6, "µrad": 1e-6, "μrad": 1e-6, "mrad": 1e-3, "rad": 1.0}
ENERGY = {"eV": 1.0, "keV": 1e3, "MeV": 1e6, "GeV": 1e9, "TeV": 1e12}

_NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

# 发射度:长度·角度 复合单位(分隔符 · * × x 空格 或无)
_EMIT = re.compile(
    rf"({_NUM})\s*(pm|nm|µm|μm|um|mm|cm|m)\s*[·*×x ]?\s*(µrad|μrad|urad|mrad|rad)\b")
# 能量
_EN = re.compile(rf"({_NUM})\s*(eV|keV|MeV|GeV|TeV)\b")
# 调谐移:Δν / tune shift / 调谐移 附近的数
_TUNESHIFT = re.compile(
    r"(?:Δν|Δν|delta\s*nu|tune\s*shift|调谐移|调谐位移)\D{0,12}?(" + _NUM + r")", re.I)


def ingest(path: Path):
    """→ [(位置标签, 文本块)]。pdf 按页,文本按行。"""
    if path.suffix.lower() == ".pdf":
        import pdfplumber
        out = []
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text() or ""
                if t.strip():
                    out.append((f"PDF p.{pg.page_number}", t))
        return out
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [(f"L{i}", ln) for i, ln in enumerate(text.splitlines(), 1) if ln.strip()]


# ---------- 机械检查 ----------
def scan(blocks):
    flags = []                  # (位置, 类型, 描述)
    emit_styles = {}            # 单位风格 -> 首次出现位置

    for loc, text in blocks:
        # 发射度:换算到 m·rad,查合理区间 + 收集单位风格
        for m in _EMIT.finditer(text):
            val, lu, au = m.group(1), m.group(2), m.group(3)
            si = float(val) * LEN[lu] * ANG[au]
            style = f"{lu}·{au}"
            emit_styles.setdefault(style, loc)
            if not (1e-13 <= si <= 1e-3):
                flags.append((loc, "数量级",
                              f"发射度 {m.group(0).strip()} ≈ {si:.1e} m·rad,"
                              f"超出合理区间 [1e-13, 1e-3] m·rad,疑似单位/数值错误"))
        # 能量:>20 TeV 超过任何现役装置
        for m in _EN.finditer(text):
            si = float(m.group(1)) * ENERGY[m.group(2)]
            if si > 2e13:
                flags.append((loc, "数量级",
                              f"能量 {m.group(0).strip()} ≈ {si:.1e} eV,超过现役加速器上限,请核对"))
        # 调谐移 |Δν|>1
        for m in _TUNESHIFT.finditer(text):
            try:
                dv = abs(float(m.group(1)))
            except ValueError:
                continue
            if dv > 1:
                flags.append((loc, "数量级",
                              f"调谐移 |Δν|={dv:g} > 1,物理上极危险/可疑(空间电荷非相干调谐移通常 ≤0.x)"))

    # 全文:发射度单位风格混用
    if len(emit_styles) > 1:
        where = ", ".join(f"{s}({l})" for s, l in emit_styles.items())
        flags.append(("全文", "单位一致性",
                      f"发射度出现多种单位风格:{where};请核对是否前后混用(mm·mrad vs m·rad 常踩)"))
    return flags


CHECKLIST = [
    "每个理论论断是否有出处 → 无出处的断言标红,要求补引用或降级为「作者推断」(走 reference_locator_policy 降级链)",
    "是否违反基本定律(Liouville / 绝热不变量 / 相空间守恒)",
    "物理直觉冲突(如「冷却的同时发射度增大」却无机制说明)",
    "公式与文字描述、图表是否自洽",
    "单位/量纲前后是否一致(可疑等式用 check_algebra.py dimension 复核)",
]


def report(path, blocks, flags) -> str:
    out = []
    out.append(f"# 文档物理审查报告:{path.name}")
    out.append(f"已扫描:{len(blocks)} 个位置块(页/行)\n")
    out.append("## ① 自动机械检查(高置信疑点)")
    if flags:
        out.append("| 位置 | 类型 | 描述 |")
        out.append("|---|---|---|")
        for loc, typ, desc in flags:
            out.append(f"| {loc} | {typ} | {desc} |")
    else:
        out.append("(本轮自动检查未发现单位/数量级类疑点)")
    out.append("\n## ② 待逐条判读(按 §6,勿略过、勿回「看起来不错」)")
    for c in CHECKLIST:
        out.append(f"- [ ] {c}")
    out.append("\n> ② 每条要落到「位置 | 问题类型 | 描述 | 出处或[缺出处]」;"
               "无出处的物理论断一律标红。")
    out.append(f"\n## 小结\n自动疑点 {len(flags)} 处;请继续完成 ② 的逐条判断后给出最终问题清单表。")
    return "\n".join(out)


# ---------- 自测 ----------
_SAMPLE = """# 束流参数(示例草稿,含植入错误)
储存环束流能量为 3 GeV,流强 300 mA,工作点 (0.31, 0.28)。
水平发射度 5 m·rad,归一化发射度 εₙ = 4 nm·rad。
注入段归一化发射度 εₙ = 2 mm·mrad。
空间电荷致非相干调谐移 Δν = 1.8,影响动力学孔径。
冷却后发射度下降一个量级。
"""


def selftest() -> int:
    print("=" * 60)
    print(" review_doc 自测(植入错误的样例草稿)")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "sample.md"
        p.write_text(_SAMPLE, encoding="utf-8")
        blocks = ingest(p)
        flags = scan(blocks)
        print(report(p, blocks, flags))
    print("\n" + "-" * 60)
    types = {t for _, t, _ in flags}
    need = {"数量级", "单位一致性"}
    ok = need <= types and any("5" in d and "m·rad" in d for _, _, d in flags) \
        and any("1.8" in d or "Δν" in d for _, _, d in flags)
    print("自测结论:", "✓ 机械检查抓到植入的量纲/数量级/单位混用错误"
          if ok else "✗ 漏判,需检查规则")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="文档物理审查(能力 C)")
    ap.add_argument("file", nargs="?", help="待审查文档 (.md/.txt/.tex/.pdf)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.file:
        ap.error("给一个文件,或用 --selftest")
    p = Path(a.file)
    if not p.exists():
        sys.exit(f"文件不存在:{p}")
    blocks = ingest(p)
    print(report(p, blocks, scan(blocks)))


if __name__ == "__main__":
    main()
