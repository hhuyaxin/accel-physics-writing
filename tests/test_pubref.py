"""能力 A 第2级 + 数据层不变量:命中给已核实 DOI,离题降级,绝不返回无 DOI 的条目。"""
import re
import pubref
import _config as C
import yaml


def _index():
    return yaml.safe_load((C.references_dir() / "public_reference_index.yaml").read_text(encoding="utf-8"))


def test_in_topic_returns_papers():
    out = pubref.search("free electron laser undulator")
    assert len(out["papers"]) >= 1


def test_off_topic_returns_no_papers():
    out = pubref.search("machine learning neural network")
    assert out["papers"] == []


def test_returned_papers_all_have_doi():
    for q in ("space charge", "synchrotron radiation", "linac"):
        for p in pubref.search(q)["papers"]:
            assert p.get("doi"), f"{p.get('title')} 返回时缺 DOI"


def test_index_every_paper_has_valid_doi():
    data = _index()
    assert data["papers"], "papers 不应为空"
    for p in data["papers"]:
        assert p.get("doi"), f"{p.get('title')} 缺 DOI(不伪造红线:宁可不收也要有真 DOI)"
        assert re.match(r"^10\.\d{4,9}/\S+$", p["doi"]), f"DOI 格式可疑:{p['doi']}"


def test_index_venues_have_http_urls():
    for v in _index()["venues"]:
        assert str(v.get("url", "")).startswith("http"), f"{v.get('id')} 缺合法 url"
