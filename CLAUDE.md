# CLAUDE.md — 加速器物理科研写作助手(项目记忆)

> 这是项目记忆文件,Claude Code 每次在本项目启动时自动读取。
> 它定义了这个 skill 的目标、架构、不可逾越的红线,以及分步构建计划。
> **在动任何代码或写任何文件前,先读完本文件。**

---

## 0. 一句话目标

构建一个 Claude Code skill:当我写论文或做 PPT 时,问加速器物理概念、设计实验、或需要理论依据(例如"为什么会束损"),它给我**有出处、可核实的答案而非猜测**,能**机械地检查我的推导是否正确**,并能**通读整份文档/讲稿、标出违反物理直觉或理论错误的地方**。

技能名(目录名 / frontmatter `name`):`accel-physics-writing`

---

## 1. 最重要的设计前提:LLM 自己分不清"知道"和"猜"

模型生成一句正确陈述和生成一句幻觉,内部机制相同,它不会自知哪句可靠。
**因此"不猜测"不能靠提示词,只能靠"答案来自可检索语料,检索不到就强制降级声明"。**

这条决定了整个架构:必须有一个**真实的、可检索的本地语料库 + 页码级溯源**。
没有这一层,"正确的书籍指向"就是空话——模型只会从训练记忆里编章节号。

---

## 2. 架构:公开 skill + 私有语料(版权红线)

```
项目根/
├── CLAUDE.md                      # 本文件,提交
├── .gitignore                     # 提交(必须先写好)
├── LICENSE                        # 提交(MIT,见 §2 许可证一节)
├── .claude/
│   └── skills/
│       └── accel-physics-writing/
│           ├── SKILL.md                    # 提交
│           ├── setup.sh                     # 提交(首次运行:装依赖 + 下载本地 embedding 模型)
│           ├── references/
│           │   ├── reference_locator_policy.md   # 提交(规则,非内容)
│           │   ├── derivation_checks.md          # 提交
│           │   ├── document_review_checklist.md  # 提交
│           │   ├── glossary_zh_en.md             # 提交(术语表)
│           │   ├── concept_map.md                # 提交(概念地图)
│           │   └── public_reference_index.yaml   # 提交(开放获取索引,零书可用,见 §2.5)
│           ├── scripts/
│           │   ├── _config.py              # 提交(单一真相源:模型名/路径/离线加载,各脚本共用)
│           │   ├── fetch_model.py          # 提交(下载本地 embedding 模型:国内走 ModelScope 直连,HF 兜底)
│           │   ├── index_corpus.py         # 提交(建索引:PDF 逐页抽取保留页码 → 切块 → 向量 → faiss)
│           │   ├── retrieve.py             # 提交(第1级检索:查私有书,返回片段+真实页码+书名)
│           │   ├── pubref.py               # 提交(第2级检索:查开放获取索引,返回已核实 DOI/站点)
│           │   └── check_algebra.py        # 提交(sympy 代数/量纲验证)
│           └── vendor/                      # 提交(内联的第三方代码,各带其 LICENSE)
│               └── README.md               # 说明每个内联组件来源与许可证
├── private_corpus/                # 整个目录 .gitignore,绝不提交
│   ├── books/                     # 我合法持有的教科书 PDF
│   ├── index/                     # 本地检索索引(向量),由 index_corpus.py 生成
│   └── private_reference_index.yaml
└── .cache/                        # .gitignore,本地 embedding 模型权重缓存(setup.sh 下载)
```

### 版权红线(不可违反)
- **可以提交、可以公开**:书目索引、概念→页码的对应表、术语表、公式(数学事实)、检查规则、检索/建索引脚本本身。这些是事实性元数据或工具,等同图书馆卡片目录。
- **绝不提交、绝不批量复述给无权限用户**:书的 PDF 全文、整页正文、原文摘录文字、由书正文生成的向量索引(`private_corpus/index/` 里可能反推出正文,故一并 gitignore)。
- 给用户"见某书第 X 页"这种**指向**永远合法;复制那几页的**内容**才侵权。
- `.gitignore` 必须在放任何书进去之前就写好,至少包含:`private_corpus/`、`*.pdf`、`*.epub`、`private_*`、`.cache/`。

### 2.4 许可证与依赖选型(影响能否干净开源)
- **本项目许可证:MIT**(放 `LICENSE`)。简单、与下方依赖兼容、便于他人复用。
- **PDF 解析用 `pdfplumber`(MIT)或 `pypdf`(BSD),不要用 PyMuPDF。** PyMuPDF 是 AGPL v3,传染性强,一旦开源重分发会污染整个项目许可证。pdfplumber/pypdf 逐页读取同样原生带页码(`page.page_number` / 枚举页索引),许可证干净。
- **embedding 必须本地、离线**:用 `sentence-transformers`(Apache-2.0)的本地模型。默认选**多语种** `paraphrase-multilingual-MiniLM-L12-v2`(中英混合语料),**绝不**用需要云端 API key 的方案(Cohere/OpenAI/Voyage)。理由有二:(1) 私有书文本不出本机,守住版权与隐私;(2) 用户无需配任何 API key。多语种模型用 SentencePiece 分词,依赖须含 `sentencepiece` + `protobuf`。
- **模型下载来源**:由 `scripts/fetch_model.py` 处理。国内 + 系统代理(Clash 等)环境下,HuggingFace/transformers 下载栈对大权重必断,`hf-mirror.com` 又只镜像小文件元数据(大 LFS 308 跳回 HF),故**国内走 ModelScope(魔搭)直连禁代理**,国外退回 HuggingFace。按文件 Size + JSON 完整性校验,防截断残档。详见项目记忆 cn-network-model-download。
- **向量检索用 `faiss-cpu`(MIT)**;符号检查用 `sympy`(BSD)。
- **内联的第三方代码**:若从 MIT 项目(如参考架构 AesZenz/zotero-rag-assistant)借用代码,拷进 `vendor/` 并保留其 LICENSE 与版权声明,在 `vendor/README.md` 注明来源。这样用户只装本 skill 一个,无需另装别人的插件。

### 2.5 公开层"零书可用"原则
公开仓库发出去后,**任何用户不放任何私有书就能立刻用到的部分**,称为公开层:
- `public_reference_index.yaml`:开放获取资源索引(JACoW / arXiv / CERN-CAS / USPAS),可带 DOI/链接,合规。
- `glossary_zh_en.md`、`concept_map.md`:中英术语表、概念地图。
- §5 推导检查、§6 文档审查:纯逻辑,不依赖任何书。
这意味着 skill 必须**没有私有语料也能降级运行**(走 §4 的第 2/3/4 级),而不是没有书就报错。私有书页码定位(§4 第 1 级)是"用户放入自己的书后解锁"的增强功能,不是运行前提。

---

## 3. 三大核心能力 + 各自的可靠性机制

### 能力 A:有出处、不猜的物理回答
机制 = 检索 + 强制分级降级(见 §4 的 locator policy)。
工作流:把宽问题展开成候选清单 → 每条去本地语料检索 → 命中给页码,未命中显式标注。
例:"为什么会束损" → 展开为(动力学孔径 / 束气散射 / Touschek / 束内散射 / 共振穿越 / RF 俘获损失 / 空间电荷 …)→ 逐条溯源。

### 能力 B:推导核查(靠机械检查,不靠 AI 直觉)
绝不让模型"凭感觉"判对错。改为运行固定检查(见 §5)。

### 能力 C:文档/PPT 物理审查(靠固定 checklist)
对整份文档跑结构化扫描,输出**问题清单 + 每条出处/缺出处标记**,而不是"看起来不错"(见 §6)。

---

## 4. reference_locator_policy(降级链——这是 skill 的灵魂)

每个理论性回答必须按以下优先级降级,且**每条结论都带来源等级标签**:

1. **命中私有语料** → 给 书名 + 章节 + 页码,标 `[私有参考·可验证]`(页码来自真实 PDF 检索,不得来自记忆)
2. **私有未命中,开放获取命中** → 给 JACoW / arXiv / CERN-CAS / USPAS 链接或 DOI,标 `[开放获取·可访问]`
3. **都未命中但属标准概念** → 可联网搜索,但必须标来源可靠性,优先官方实验室与同行评审,拒绝论坛,标 `[网络来源·已核来源]`
4. **确无权威出处** → 明说"无可靠出处,以下为基于物理原理的推断",标 `[推断·未经文献核实]`

**铁律:任何情况下都不得伪造页码、不得编造 DOI。** 宁可标 4 级,不可假装 1 级。

---

## 5. derivation_checks(推导机械检查流程)

收到任何推导时,逐项执行,把每项结果列出来:

- **量纲检查**:每个等式两边量纲是否一致(eV vs J、归一化 vs 几何发射度等常错点)。
- **极限/特例检查**:令关键参数趋 0 或趋 ∞,结果是否退回已知简单情形(如空间电荷项归零应退回单粒子运动)。
- **守恒/符号检查**:能量、动量、相空间体积(Liouville)是否守恒;符号约定是否自洽。
- **符号代数验证**:调用 `scripts/check_algebra.py`(sympy)真算一遍化简,不靠心算。
- **数量级检查**:代入典型数值,结果量级是否物理合理。

输出格式:每步 ✓/✗ + 简述;发现问题给出具体位置和建议,而非笼统结论。

---

## 6. document_review_checklist(整篇文档/PPT 审查)

对全文逐条扫描,产出一张表:`位置 | 问题类型 | 描述 | 出处或[缺出处]`。

- 单位/量纲前后是否一致
- 数量级是否合理(束流能量、流强、亮度、发射度的典型范围)
- 是否违反基本定律(Liouville、绝热不变量、相空间守恒)
- 物理直觉冲突(如"冷却的同时发射度增大"却无机制说明)
- **每个理论论断是否有出处** → 无出处的断言标红,要求补引用或降级为"作者推断"
- 公式与文字描述是否自洽

---

## 7. 来源等级标签(全项目统一)

```
[私有参考·可验证]      —— 来自本地教科书,带页码
[开放获取·可访问]      —— JACoW / arXiv / CAS / USPAS,带链接或 DOI
[网络来源·已核来源]    —— 联网得到,已标可靠性
[推断·未经文献核实]    —— 模型推断,无出处
```

---

## 7.5 交付形态:内联薄检索 + 本地 embedding + 公开层零书可用

这一节定义"用户只装我这一个 skill"如何实现,以及对两类用户分别交付什么。

### 用户分两类(交付内容不同)
- **作者本人(有完整私有语料)**:四级全部可用,含私有书页码定位。
- **开源用户(无我的书)**:装上即用公开层(开放获取索引、术语表、概念图、推导检查、文档审查)。私有书页码定位需他们放入**自己合法持有的书**并跑一次建索引。**永远不分发书本身。**

### 三个配置要尽量趋近于零
1. **不需要 API key** —— 因为 embedding 用本地 `sentence-transformers` 模型,全程离线。
2. **依赖自动装** —— Python 包(pdfplumber / sentence-transformers / faiss-cpu / sympy)装不进 skill 文件夹,故由 `setup.sh` 在首次运行时自动 `pip install` 并下载本地 embedding 模型到 `.cache/`。SKILL.md 里应在首次使用检索前检查依赖是否就绪,缺失则提示运行 `setup.sh`。
3. **唯一真正需要用户手动做的一步** —— 放入自己的书并跑 `index_corpus.py`。这一步无法替用户免除(版权),但要用清晰文档把它降到"拷 PDF 进目录 + 跑一条命令"。

### retrieve.py 的检索链(全离线、页码精确)
```
PDF ──pdfplumber逐页读取──> (页码, 页文本)
       │  保留 page 号,这是"第 X 页"的唯一可信来源,不来自模型记忆
       ▼
   滑窗切块(每块附带其所属页码;跨页块记起止页)
       ▼
 sentence-transformers 本地模型 ──> 向量
       ▼
   faiss-cpu 建/查索引(存 private_corpus/index/,gitignore)
       ▼
 查询时:返回 top-k 片段 + 每片段的真实页码 + 书名
```
关键约束:**每个返回片段必须携带其页码**;检索不到达阈值就返回空,触发 §4 的降级,而不是硬凑。retrieve.py 只返回"片段+页码+出处",**不返回整页正文**,避免把书内容写进任何可提交位置。

### vendor/ 内联原则
- 只在确有现成 MIT/BSD/Apache 代码可省事时才内联;能自己写薄脚本就自己写(更可控、依赖更少)。
- 内联任何代码,必须在 `vendor/<组件>/` 内保留原 LICENSE 文件,并在 `vendor/README.md` 记一行:来源 URL、许可证、内联日期、改了什么。
- 不内联 AGPL 代码(同 §2.4,会污染许可证)。

---

## 8. 分步构建计划(MVP)

按顺序做,每步做完让我确认再进下一步。

**Step 1 — 立骨架与红线**
- 先写好 `.gitignore`(见 §2,含 `private_corpus/`、`*.pdf`、`.cache/` 等),再建目录结构。
- 放 `LICENSE`(MIT)。
- 用 skill-creator 规范写 `SKILL.md`:frontmatter 的 `description` 要"略微强势"以保证触发(覆盖"概念解释/设计实验/理论依据/查推导/审文档"等措辞)。body 里指向 §4/§5/§6 三个 references 文件,并说明首次使用检索前需跑 `setup.sh`。
- 把 §4、§5、§6、§7 的内容落成对应的 references/*.md 文件。

**Step 1.5 — 写 setup.sh 与依赖基线**
- `setup.sh`:`pip install pdfplumber sentence-transformers faiss-cpu sympy`(均 MIT/BSD/Apache,不要 PyMuPDF),并预下载本地 embedding 模型到 `.cache/`。
- 验证:全程不需要任何 API key,断网也能装好模型后运行。

**Step 2 — 打通"私有 PDF → 页码"这条链(最关键,先小后大)**
- 只拿 1 本书(如 Hofmann)放进 `private_corpus/books/`。
- 写 `scripts/index_corpus.py`(pdfplumber 抽页码+切块+本地 embedding+faiss 建索引)与 `scripts/retrieve.py`(查询→返回片段+真实页码+书名),实现 §7.5 的检索链。
- 最小验证:问一个明确概念,核对返回页码是否正确。**这一步通过前不要批量导入书。**
- 同时验证**零书可用**:在没有任何私有书的情况下跑一次,确认 skill 正常降级到 §4 第 2/3/4 级,而不是报错。
- 通过后再扩到核心书单:Wiedemann、S.Y. Lee、Reiser、Chao(及中文教材/院校讲义)。

**Step 3 — 推导检查**
- 写 `scripts/check_algebra.py`(sympy),实现 §5 的量纲/化简验证。
- 用一个我给的真实推导测一遍。

**Step 4 — 文档审查**
- 实现 §6 的 checklist 扫描,先拿我的一份旧 PPT/草稿试跑,看产出的问题清单是否有用。

**Step 5 — 公开层**
- 填 `public_reference_index.yaml`(书目+页码段,合规)、`glossary_zh_en.md`、`concept_map.md`。
- 确认公开仓库里没有任何正文内容后,才可推到 GitHub。

---

## 9. 给 Claude Code 的常驻提醒

- 任何理论回答都必须带 §7 的来源等级标签。
- 不确定就标 `[推断·未经文献核实]`,不要假装有出处。
- 涉及推导一律走 §5 的机械检查,不要凭直觉下结论。
- 改动 SKILL.md 前先读它;创建文件前先确认 `.gitignore` 已生效。
- PDF 解析只用 pdfplumber/pypdf,embedding 只用本地 sentence-transformers,绝不引入 PyMuPDF 或任何需要云端 API key 的依赖(许可证 + 隐私 + 零配置三重原因)。
- 任何功能都要保证"零私有书也能降级运行";不要写出"没有书就报错"的逻辑。
- retrieve.py 只返回片段+页码+出处,绝不把整页正文写入任何可提交文件或回复给无权限用户。
- 任何会把书籍正文写进可提交文件的操作,先停下来问我。

---

## 10. 用户安装与使用(README 蓝本)

这一节是给"装这个 skill 的人"看的契约,后续据此生成 `README.md`。目标:手动步骤压到最少,且不碰版权。

### 装上后立刻可用(零私有书)
克隆/安装 skill → 跑一次 `setup.sh` → 公开层全部可用:
- 加速器物理概念问答(降级到开放获取来源 + 标注来源等级)
- 中英术语对照、概念地图
- 推导机械检查(量纲/极限/守恒/sympy 代数)
- 文档/PPT 物理审查
此时回答永远带 §7 来源等级标签;凡无私有书可溯源处,如实标 `[开放获取·可访问]` / `[网络来源·已核来源]` / `[推断·未经文献核实]`。

### 解锁"私有书页码定位"(可选增强,用户自备书)
1. 把**自己合法持有的** PDF 放进 `private_corpus/books/`。
2. 跑 `python .claude/skills/accel-physics-writing/scripts/index_corpus.py`。
3. 之后相关问题会优先给 `[私有参考·可验证]` + 书名 + 页码。
> 本项目**不分发任何书籍**;页码定位只对用户自己提供的书生效。这是法律上唯一干净的形态。

### 安装步骤一览(写进 README)
```
# 1. 安装 skill(plugin marketplace 或手动拷入 .claude/skills/)
# 2. 一次性初始化(装依赖 + 下载本地 embedding 模型,无需任何 API key)
bash .claude/skills/accel-physics-writing/setup.sh
# 3.(可选)放入自己的书并建索引
cp your_books/*.pdf private_corpus/books/
python .claude/skills/accel-physics-writing/scripts/index_corpus.py
```

### 系统要求(写进 README)
- Python 3.10+
- 首次 `setup.sh` 需联网下载依赖与本地模型;之后检索/问答全程离线。
- 无需任何云端 API key。
- 磁盘:本地 embedding 模型约数百 MB,存于 `.cache/`(已 gitignore)。

### 给用户的明确边界(写进 README,避免误解)
- 开箱即用的是"工具 + 公开索引 + 检查能力",不是一个内置书库的问答机。
- "对着某书第 X 页"这类回答,需用户先放入自己拥有的那本书。
- 任何回答都带来源等级;看到 `[推断·未经文献核实]` 即表示该结论无文献背书,请自行核实。
