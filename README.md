# accel-physics-writing

> 加速器物理 / 束流动力学 **科研写作助手**(Claude Code skill)
> An accelerator-physics & beam-dynamics **scientific-writing assistant** for Claude Code.
>
> **作者 / Author:** Yaxin Hu (胡雅欣) · GitHub [@hhuyaxin](https://github.com/hhuyaxin)

写论文 / PPT / 讲稿时,问加速器物理概念、要理论依据("为什么会束损")、查推导、审文档——
它给你**有出处、可核实的答案而非猜测**:命中私有教科书时**精确到页码**,否则降级到**已核实的开放获取文献**,
并对每条结论标注**来源等级**。

**English summary**: A Claude Code skill that answers accelerator-physics questions for scientific writing
with *verifiable sources, not guesses*. It cites page numbers from your own legally-owned textbooks (indexed
locally, fully offline) and falls back to verified open-access references (CERN-CAS / JUAS / PRAB, with real
DOIs). Every claim carries a source-reliability tag. **No book is ever distributed** — page-level citation
only works on books *you* provide.

---

## 核心理念:为什么"不猜"靠机制而非语气

LLM 生成一句正确陈述和生成一句幻觉,内部机制相同,模型不会自知哪句可靠。所以本 skill 的"不猜"
不靠提示词,而靠**真实可检索的本地语料 + 强制分级降级**。每条理论结论都带一个标签:

```
[私有参考·可验证]    来自你本地教科书,带真实页码(向量检索,非记忆)
[开放获取·可访问]    CERN-CAS / JUAS / PRAB / arXiv,带已核实的真实 DOI
[网络来源·已核来源]  联网得到,已标可靠性
[推断·未经文献核实]  模型推断,无出处 —— 看到它就请自行核实
```

**铁律:绝不伪造页码、绝不编造 DOI。** 检索不到就如实降级,而不是硬凑。

---

## 两种用法

### A. 装上即用(零私有书)
克隆 → 跑一次 `setup.sh` → 公开层立即可用:
- 加速器物理概念问答(降级到**已核实**的开放获取文献 + 来源等级标签)
- 中英术语对照(105 词)、概念关系图
- 推导机械检查、文档物理审查的规则框架

此时回答永远带来源等级;无私有书可溯源处如实标 `[开放获取·可访问]` / `[推断·未经文献核实]`。

### B. 解锁"私有书页码定位"(可选,用户自备书)
1. 把**你自己合法持有的** PDF 放进 `private_corpus/books/`
2. 跑 `index_corpus.py` 建本地索引
3. 之后相关问题优先给 `[私有参考·可验证]` + 书名 + 页码

> **本项目不分发任何书籍**;页码定位只对你自己提供的书生效。这是法律上唯一干净的形态。

---

## 安装

```bash
# 1. 安装 skill(拷入 .claude/skills/ 或经 plugin marketplace)
# 2. 一次性初始化:建 .venv、装依赖、下载本地 embedding 模型(无需任何 API key)
bash .claude/skills/accel-physics-writing/setup.sh

# 3.(可选)放入自己的书并建索引,解锁页码定位
cp 你的书.pdf  private_corpus/books/
.venv/bin/python .claude/skills/accel-physics-writing/scripts/index_corpus.py
```

### 系统要求
- Python 3.10+(setup.sh 会自动探测 3.10+ 解释器,无需手动切换)
- 首次 `setup.sh` 需联网下载依赖与本地模型(约数百 MB,存于 `.cache/`);之后**检索/问答全程离线**
- **无需任何云端 API key**(embedding 用本地 `sentence-transformers` 多语种模型)

### 🇨🇳 国内网络说明
setup.sh 已内置国内可靠方案:
- 模型下载自动走 **ModelScope(魔搭)直连**(HF/hf-mirror 对大文件不稳,已规避)
- pip 可用清华源:`PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash setup.sh`

---

## 三大能力现状(诚实标注)

| 能力 | 状态 | 说明 |
|---|---|---|
| **A. 有出处的物理问答** | ✅ 可用 | 私有书页码级 + 公开站点级降级链全通 |
| B. 推导机械检查(量纲/化简) | 🚧 规则就绪,脚本开发中 | `scripts/check_algebra.py` 待实现 |
| C. 文档/PPT 物理审查 | 🚧 规则就绪,脚本开发中 | checklist 已有,扫描脚本待实现 |

公开开放获取文献库目前 **17 篇全部联网核实真实 DOI**,覆盖空间电荷、横/纵向动力学、同步辐射、
直线加速器、集体效应、超导 RF、自由电子激光、能量回收直线、正负电子对撞机、注入引出、等离子体尾场、束流诊断。

---

## 目录结构

```
.claude/skills/accel-physics-writing/
├── SKILL.md                 # 技能定义与触发
├── setup.sh                 # 首次初始化(装依赖+下模型,无需 API key)
├── references/              # 规则与公开资料(可提交)
│   ├── reference_locator_policy.md   # 降级链(skill 的灵魂)
│   ├── derivation_checks.md          # 推导机械检查流程
│   ├── document_review_checklist.md  # 文档审查 checklist
│   ├── glossary_zh_en.md             # 中英术语表
│   ├── concept_map.md                # 概念关系图
│   └── public_reference_index.yaml   # 开放获取索引(已核实 DOI)
└── scripts/
    ├── _config.py           # 单一真相源
    ├── fetch_model.py       # 下模型(国内走 ModelScope)
    ├── index_corpus.py      # 私有 PDF → 带页码的向量索引
    ├── retrieve.py          # 第1级检索:私有书 → 片段+页码
    └── pubref.py            # 第2级检索:开放获取索引 → 已核实 DOI

private_corpus/   # 你的书与索引,整目录 .gitignore,绝不提交
```

---

## 版权边界(请务必理解)
- 开箱即用的是"**工具 + 公开索引 + 检查规则**",**不是**一个内置书库的问答机。
- "对着某书第 X 页"这类回答,需你先放入**自己拥有**的那本书。
- 给"见某书第 X 页"的**指向**永远合法(=学术引用);本项目**不复制、不分发**书的正文内容。
- 任何回答都带来源等级标签;看到 `[推断·未经文献核实]` 即表示该结论无文献背书。

## 作者 / Author
**Yaxin Hu(胡雅欣)** — GitHub [@hhuyaxin](https://github.com/hhuyaxin)
如果这个 skill 对你的科研写作有帮助,欢迎 Star ⭐ 与引用。

## 许可证
[MIT](LICENSE) © 2026 Yaxin Hu
