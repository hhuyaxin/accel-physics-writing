#!/usr/bin/env python3
"""
fetch_model.py —— 把本地 embedding 模型下载到一个本地目录,供离线加载。

为什么不直接用 sentence-transformers 自带下载?
  实测在中国大陆 + 系统代理(如 Clash)环境下,huggingface_hub/transformers 的下载栈
  会绕过代理直连 huggingface.co 而失败;而 hf-mirror.com 只镜像小文件元数据,大的 LFS
  权重会 308 跳回 huggingface.co,同样失败。唯一稳的是 ModelScope(魔搭,阿里云,国内直连)。

策略(source=auto 时):
  先试 ModelScope 直连(禁代理),不通再退回 HuggingFace(适合国外用户)。

产物:一个可被 SentenceTransformer(local_dir) 直接离线加载的目录。
依赖:仅标准库(urllib/json)。不引入 modelscope 包,保持依赖最小。
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

# 跳过这些冗余格式/目录(我们只用 PyTorch + safetensors)
SKIP_SUBSTR = ("tf_model", ".h5", ".onnx", "onnx/", "openvino", "flax",
               "rust_model", ".msgpack", ".ot")
SKIP_DIRS = {"onnx", "openvino", ".cache"}

MODELSCOPE = "https://www.modelscope.cn"


def _opener(use_proxy: bool):
    """禁代理(ModelScope 国内直连)或允许环境代理(HF)。"""
    if use_proxy:
        return urllib.request.build_opener()  # 默认读环境代理
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 强制直连


def _get(url: str, opener, timeout=30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "accel-physics-writing/1.0"})
    with opener.open(req, timeout=timeout) as r:
        return r.read()


# ---------------- ModelScope ----------------
def ms_list_files(model: str, opener) -> list[dict]:
    """递归列出 ModelScope 仓库所有 blob 文件(含子目录)。"""
    out: list[dict] = []

    def walk(root: str):
        url = f"{MODELSCOPE}/api/v1/models/{model}/repo/files?Revision=master"
        if root:
            url += f"&Root={root}"
        data = json.loads(_get(url, opener))
        for f in data.get("Data", {}).get("Files", []):
            path, typ, size = f.get("Path"), f.get("Type"), f.get("Size", 0)
            if typ == "tree":
                if path.split("/")[-1] in SKIP_DIRS:
                    continue
                walk(path)
            elif typ == "blob":
                out.append({"path": path, "size": size})

    walk("")
    return out


def ms_file_url(model: str, path: str) -> str:
    return f"{MODELSCOPE}/api/v1/models/{model}/repo?Revision=master&FilePath={path}"


def filter_files(files: list[dict]) -> list[dict]:
    keep = [f for f in files if not any(s in f["path"] for s in SKIP_SUBSTR)]
    # 有 safetensors 就不下 pytorch_model.bin,省一半流量
    if any(f["path"].endswith("model.safetensors") for f in keep):
        keep = [f for f in keep if not f["path"].endswith("pytorch_model.bin")]
    return keep


def download_one(url, dest: Path, expect_size: int, opener, retries=6) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 幂等:大小已对就跳过
    if dest.exists() and expect_size and dest.stat().st_size == expect_size:
        print(f"  = {dest.name} 已存在且大小一致,跳过")
        return
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "accel-physics-writing/1.0"})
            with opener.open(req, timeout=1800) as r, open(dest, "wb") as fh:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
            got = dest.stat().st_size
            if expect_size and got != expect_size:
                raise IOError(f"大小不符: 期望 {expect_size}, 实得 {got}")
            if dest.suffix == ".json":
                json.load(open(dest))  # 校验 JSON 完整(踩过截断的坑)
            print(f"  ↓ {dest.name}  {got} bytes  ✅")
            return
        except Exception as e:  # noqa
            last = e
            print(f"  ↻ {dest.name} 第{attempt}次失败: {str(e)[:80]}")
            time.sleep(3)
    raise RuntimeError(f"下载失败 {dest}: {last}")


def fetch_modelscope(model: str, dest: Path) -> bool:
    opener = _opener(use_proxy=False)  # 魔搭国内直连,禁代理
    try:
        files = filter_files(ms_list_files(model, opener))
    except Exception as e:  # noqa
        print(f"  ModelScope 列文件失败: {str(e)[:120]}")
        return False
    if not files:
        print("  ModelScope 未列到文件")
        return False
    print(f"  ModelScope 命中 {len(files)} 个文件,开始下载(直连不走代理)...")
    for f in files:
        download_one(ms_file_url(model, f["path"]), dest / f["path"], f["size"], opener)
    return True


# ---------------- HuggingFace 兜底(国外用户)----------------
def fetch_huggingface(model: str, dest: Path) -> bool:
    """国外/可直连 HF 的用户:用 sentence-transformers 正常下载并落到本地目录。"""
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(model)        # 走 HF 默认下载
        m.save(str(dest))                     # 落成本地离线目录
        return True
    except Exception as e:  # noqa
        print(f"  HuggingFace 下载失败: {str(e)[:160]}")
        return False


def verify(dest: Path) -> bool:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(str(dest))
    v = m.encode(["space charge tune shift", "空间电荷调谐移"])
    ok = len(v) == 2 and len(v[0]) > 0
    print(f"  离线加载验证: 维度={len(v[0])}  {'✅' if ok else '❌'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="模型仓库 id")
    ap.add_argument("--dest", required=True, help="落地目录")
    ap.add_argument("--source", default="auto", choices=["auto", "modelscope", "huggingface"])
    args = ap.parse_args()
    dest = Path(args.dest)

    order = {"auto": ["modelscope", "huggingface"],
             "modelscope": ["modelscope"],
             "huggingface": ["huggingface"]}[args.source]

    ok = False
    for src in order:
        print(f"→ 尝试来源: {src}")
        ok = fetch_modelscope(args.model, dest) if src == "modelscope" else fetch_huggingface(args.model, dest)
        if ok:
            print(f"✅ 模型文件已就位({src}) → {dest}")
            break
    if not ok:
        print("❌ 所有来源均失败。请检查网络;国外用户可加 --source huggingface,国内用 --source modelscope。", file=sys.stderr)
        sys.exit(1)
    if not verify(dest):
        sys.exit(2)
    print("✅ 模型可离线加载,完成。")


if __name__ == "__main__":
    main()
