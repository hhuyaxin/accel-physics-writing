"""能力 C 不变量:机械抓单位/数量级疑点,且不对正常文档误报。"""
import review_doc as rd


def _flags(text, tmp_path):
    p = tmp_path / "d.md"
    p.write_text(text, encoding="utf-8")
    return rd.scan(rd.ingest(p))


def test_flags_absurd_emittance(tmp_path):
    flags = _flags("水平发射度 5 m·rad,影响亮度。", tmp_path)
    assert any(t == "数量级" and "m·rad" in d for _, t, d in flags)


def test_flags_large_tune_shift(tmp_path):
    flags = _flags("空间电荷致非相干调谐移 Δν = 1.8。", tmp_path)
    assert any("Δν" in d or "1.8" in d for _, _, d in flags)


def test_flags_emittance_unit_mixing(tmp_path):
    flags = _flags("εₙ = 4 nm·rad\n注入段 εₙ = 2 mm·mrad", tmp_path)
    assert any(t == "单位一致性" for _, t, _ in flags)


def test_no_false_positive_on_plausible_doc(tmp_path):
    flags = _flags("归一化发射度 εₙ = 2 mm·mrad,能量 3 GeV,流强 300 mA。", tmp_path)
    assert not any(t == "数量级" for _, t, _ in flags)


def test_selftest_passes():
    assert rd.selftest() == 0
