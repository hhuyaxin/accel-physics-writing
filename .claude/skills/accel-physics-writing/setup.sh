#!/usr/bin/env bash
# ============================================================
#  accel-physics-writing —— 首次初始化脚本(每个用户跑一次)
#  见 CLAUDE.md §2.4 / §7.5 / §8 Step 1.5
#
#  做两件事,全程无需任何 API key:
#    ① 在项目根建 .venv 隔离环境,装 4 个依赖(均 MIT/BSD/Apache,禁 PyMuPDF)
#    ② 把本地 embedding 模型预下载到 .cache/(之后断网也能用)
#
#  幂等:可重复运行;.venv 已存在则复用。
# ============================================================
set -euo pipefail

# ---- 0. 定位数据落地根(决定 skill 能否被随意安装)----
#   SCRIPT_DIR = 本 skill 目录(setup.sh 就在 skill 根)。
#   DATA_ROOT(.venv / .cache / private_corpus 落地处)解析优先级:
#     1) 环境变量 APW_HOME;
#     2) 开发仓库:向上找到含 CLAUDE.md 的目录 → 用仓库根(现有布局不变);
#     3) 别人安装(无 CLAUDE.md)→ 自包含在 skill 目录内。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT=""
if [ -n "${APW_HOME:-}" ]; then
  PROJECT_ROOT="$(cd "$APW_HOME" && pwd)"
else
  d="$SCRIPT_DIR"
  while [ "$d" != "/" ]; do
    [ -f "$d/CLAUDE.md" ] && { PROJECT_ROOT="$d"; break; }
    d="$(dirname "$d")"
  done
  [ -z "$PROJECT_ROOT" ] && PROJECT_ROOT="$SCRIPT_DIR"   # 自包含
fi
VENV_DIR="$PROJECT_ROOT/.venv"
CACHE_DIR="$PROJECT_ROOT/.cache"

# ---- 选型:本地 embedding 模型 ----
#  默认用多语种小模型:语料/提问是中英混合(英文教科书 + 中文教材),
#  纯英文的 all-MiniLM 对中文召回差,故选 multilingual。
#  可用环境变量覆盖,例如:EMB_MODEL=sentence-transformers/all-mpnet-base-v2 bash setup.sh
#  ⚠️ Step 2 的 index_corpus.py / retrieve.py 必须用同一个模型,否则向量不可比。
EMB_MODEL="${EMB_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"

echo "============================================================"
echo " accel-physics-writing 初始化"
echo " 项目根 : $PROJECT_ROOT"
echo " 虚拟环境: $VENV_DIR"
echo " 模型缓存: $CACHE_DIR"
echo " embedding 模型: $EMB_MODEL"
echo "============================================================"

# ---- 1. 自动挑一个 Python 3.10+ 解释器 ----
#   macOS 上 `python3` 常是系统自带的 3.9,但用户多半另装了新版。
#   依次尝试候选,选第一个满足 3.10+ 的;可用 PYTHON 环境变量强制指定。
#   例:PYTHON=/Users/me/miniconda3/bin/python3 bash setup.sh
BASE_PY=""
for cand in "${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3; do
  [ -z "$cand" ] && continue
  command -v "$cand" >/dev/null 2>&1 || continue
  if "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
    BASE_PY="$cand"
    break
  fi
done
if [ -z "$BASE_PY" ]; then
  echo "❌ 未找到 Python 3.10+。系统 python3 太旧或不存在。" >&2
  echo "   解决:装一个新版 Python(如 python.org 安装包),或用 PYTHON 指定已有的:" >&2
  echo "        PYTHON=/path/to/python3.12 bash setup.sh" >&2
  exit 1
fi
echo "✅ 使用 Python: $("$BASE_PY" --version) ($(command -v "$BASE_PY"))"

# ---- 2. 建 / 复用 .venv ----
if [ ! -d "$VENV_DIR" ]; then
  echo "→ 用 $BASE_PY 创建虚拟环境 .venv ..."
  "$BASE_PY" -m venv "$VENV_DIR"
else
  echo "→ 复用已存在的 .venv"
fi
# 直接用 venv 内解释器,避免依赖 activate
PY="$VENV_DIR/bin/python"

# pip 抗网络抖动:加重试与超时(下载 torch 等大包时尤其重要)
PIP_FLAGS=(--retries 8 --timeout 120)
#   国内/弱网用户:直连 PyPI 与 HuggingFace 易断,可用镜像环境变量(脚本自动尊重):
#     PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
#     HF_ENDPOINT=https://hf-mirror.com \
#     bash setup.sh
#   pip 原生读 PIP_INDEX_URL;huggingface_hub 原生读 HF_ENDPOINT。不在脚本里硬写死镜像,
#   以免影响国外用户。
if [ -n "${PIP_INDEX_URL:-}" ]; then echo "→ 使用 PyPI 镜像: $PIP_INDEX_URL"; fi
if [ -n "${HF_ENDPOINT:-}" ]; then echo "→ 使用 HuggingFace 镜像: $HF_ENDPOINT"; fi

echo "→ 升级 pip ..."
"$PY" -m pip install "${PIP_FLAGS[@]}" --upgrade pip >/dev/null

# ---- 3. 装依赖(许可证均干净:MIT/BSD/Apache)----
#   pdfplumber(MIT) sentence-transformers(Apache-2.0) faiss-cpu(MIT) sympy(BSD)
#   绝不引入 PyMuPDF(AGPL,会污染 MIT)或任何需云端 key 的 embedding 方案。
echo "→ 安装依赖(首次较慢,会拉取 torch,可能数百 MB ~ 1GB)..."
#   sentencepiece + protobuf:多语种模型用 SentencePiece 分词,transformers 加载时必需。
"$PY" -m pip install "${PIP_FLAGS[@]}" \
  "pdfplumber" \
  "sentence-transformers" \
  "faiss-cpu" \
  "sympy" \
  "sentencepiece" \
  "protobuf" \
  "pyyaml"

# ---- 4. 下载本地 embedding 模型到 .cache/st-models/ ----
#   交给 fetch_model.py:国内自动走 ModelScope 直连(禁代理),国外退回 HuggingFace。
#   背景:实测国内 + 系统代理下,HF/transformers 下载栈对大权重必断;魔搭直连才稳。
#   可用 MODEL_SOURCE=modelscope|huggingface|auto 指定来源(默认 auto)。
mkdir -p "$CACHE_DIR"
MODEL_BASENAME="$(basename "$EMB_MODEL")"
MODEL_DIR="$CACHE_DIR/st-models/$MODEL_BASENAME"
echo "→ 下载并验证 embedding 模型 → $MODEL_DIR"
"$PY" "$SCRIPT_DIR/scripts/fetch_model.py" \
  --model "$EMB_MODEL" \
  --dest "$MODEL_DIR" \
  --source "${MODEL_SOURCE:-auto}"

# ---- 5. 验证其余依赖可导入 ----
echo "→ 验证依赖导入 ..."
"$PY" - <<'PY'
import pdfplumber, faiss, sympy  # noqa
print("   ✅ pdfplumber / faiss / sympy 导入正常")
PY

echo "============================================================"
echo " ✅ 初始化完成。全程未使用任何 API key。"
echo "    embedding 模型目录(离线加载用):$MODEL_DIR"
echo "    之后检索/问答可离线运行。"
echo ""
echo " 下一步(可选,解锁私有书页码定位):"
echo "   cp 你的书.pdf  $PROJECT_ROOT/private_corpus/books/"
echo "   \"$PY\" $SCRIPT_DIR/scripts/index_corpus.py     # Step 2 实现后可用"
echo "============================================================"
