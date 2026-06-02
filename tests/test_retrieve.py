"""能力 A 第1级不变量:离题降级、命中带真实页码、无索引不报错。
需本地模型+索引的用例在缺失时自动 skip(别人 clone 后也能跑通其余测试)。"""
import pytest
import _config as C
import retrieve

_HAS_MODEL = C.model_dir().exists()
_HAS_INDEX = (C.index_dir() / "corpus.faiss").exists()
_needs_corpus = pytest.mark.skipif(
    not (_HAS_MODEL and _HAS_INDEX),
    reason="需本地模型与索引(先跑 setup.sh + index_corpus.py)")


def test_no_index_degrades_not_errors(tmp_path, monkeypatch):
    """无索引时应返回 no_index(交给降级链),而不是抛异常。"""
    monkeypatch.setattr(C, "index_dir", lambda: tmp_path)
    out = retrieve.retrieve("anything")
    assert out["status"] == "no_index"
    assert out["results"] == []


@_needs_corpus
def test_off_topic_degrades_no_fabrication():
    out = retrieve.retrieve("唐诗宋词的艺术鉴赏与平仄格律", k=3)
    assert out["status"] == "below_threshold"
    assert out["results"] == []          # 命脉:查不到就不硬凑


@_needs_corpus
def test_on_topic_hits_with_real_page():
    out = retrieve.retrieve("space charge tune shift", k=2)
    assert out["status"] == "ok" and out["results"]
    for r in out["results"]:
        assert r["pdf_page"] > 0 and r["book"]     # 带真实页码与出处
