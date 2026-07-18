# ResAgent — 多智能体简历筛选系统

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![Vue 3](https://img.shields.io/badge/Vue_3-Nuxt_3-4FC08D?style=flat&logo=vue.js&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C?style=flat)
![DeepSeek](https://img.shields.io/badge/DeepSeek-V4_Flash_|_Pro-4F46E5?style=flat)
![ChromaDB](https://img.shields.io/badge/ChromaDB-向量数据库-FF6F00?style=flat)
![BGE--M3](https://img.shields.io/badge/BGE--M3-Embedding-9CF?style=flat)
![BGE--Reranker](https://img.shields.io/badge/BGE--Reranker-v2--m3-9CF?style=flat)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)

**RAG + 多 Agent 协作 · BM25 + 向量混合检索 · 智能简历筛选与人才匹配平台**

</div>

---

## 🏗 架构

4 节点 LangGraph 管线，SSE 实时推送进度：

```
📋 选择岗位 + 📤 已上传简历
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Node 1: Job Analyzer                                    │
│  LLM 分析 JD → 硬性要求 + 评分权重                         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Node 2: Retriever — 多阶段混合检索                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐                              │
│  │ BM25 关键词│  │ Chroma   │  jieba 分词 + BGE-M3 向量     │
│  │ 全文检索   │  │ 语义召回  │                              │
│  └────┬─────┘  └────┬─────┘                              │
│       └──────┬──────┘  混合融合 (BM25×0.4 + 向量×0.6)     │
│              ▼                                           │
│       ┌─────────────┐                                    │
│       │ BGE-Reranker │  Cross-Encoder 精排 → Top-K       │
│       └──────┬──────┘                                    │
│              ▼                                           │
│       ┌─────────────┐                                    │
│       │  LLM 排序    │  DeepSeek 语义排序 + 去重           │
│       └─────────────┘                                    │
└───────────────────────┬─────────────────────────────────┘
                        │  Top-K 排序结果
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Node 3: Matcher — 逐一 LLM 深度匹配                       │
│  每候选人独立评估: 技能匹配 · 经验相关 · 教育 · 职业轨迹       │
│  → Dimension Scores + Gaps + Highlights + Risks          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Node 4: Bias Detector — Agent 公平性审计（Pro + thinking） │
│  批量检测: 性别 · 年龄 · 院校 · 地域 · 经验描述 五维偏见     │
│  → Fairness Score + Flags + 分布分析                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
              📊 候选人排名 + 📝 Agent 评估报告 + ⚖️ 公平性审查
```

## 🚀 快速开始

```bash
git clone https://github.com/subaoyan16/RESAgent.git
cd RESAgent

# 配置环境变量
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY

# 一键启动（需要 Docker）
docker-compose up -d

# 访问
# 前端 → http://localhost:3000
# API  → http://localhost:8000/docs
```

本地开发（不使用 Docker）：

```bash
make setup                        # pip install + 建表
make dev-backend                  # 启动后端 → http://localhost:8000
make dev-frontend                 # 启动前端 → http://localhost:3000

# 或手动执行:
pip install -r requirements.txt
python scripts/init_db.py
uvicorn api.main:app --reload
```

所有 Make 命令：

```bash
make help          # 列出所有可用目标
make test          # 运行全部测试
make lint          # ruff + mypy 检查
make format        # 代码格式化
make clean         # 清理缓存
make db-reset      # 重置数据库
make chroma-reset  # 清空向量库
```

## 🔧 技术栈

| 类别 | 技术 |
|:-----|:-----|
| 🖥️ 后端框架 | FastAPI + Python 3.12 |
| 🔗 Agent 编排 | LangGraph (4 节点 StateGraph + MemorySaver) |
| 🧠 LLM | DeepSeek V4 Flash / Pro（双模型路由，支持 Thinking 模式） |
| 🔍 混合检索 | **BM25** (jieba 分词) + **ChromaDB** (BGE-M3 向量) → 加权融合 |
| 🎯 精排 | **BGE-Reranker-v2-m3** Cross-Encoder 本地推理 |
| 🔢 Embedding | **BGE-M3** (本地 1024 维 · CPU/GPU 推理 · L2 归一化) |
| 🏗️ ORM | SQLAlchemy + SQLite (5 个模型: Candidate / Job / ScreeningTask / MatchResult / BiasReport) |
| 📄 文档解析 | PyMuPDF + python-docx |
| 📡 实时推送 | SSE (Server-Sent Events) — 后端推送 + 前端 EventSource 接收，替代轮询 |
| 🎨 前端 | Vue 3 + Nuxt 3 + Element Plus + Pinia |
| 🐳 容器化 | Docker + Docker Compose |
| 🧪 测试 | pytest + pytest-asyncio + pytest-cov |

## 🔄 检索管线详解

| 阶段 | 方法 | 说明 |
|:-----|:-----|:-----|
| 1️⃣ **关键词召回** | BM25 | jieba 中英文混合分词，全文检索 Top-20 |
| 2️⃣ **向量召回** | ChromaDB + BGE-M3 | 语义相似度搜索，余弦距离 Top-20 |
| 3️⃣ **混合融合** | Weighted Fusion | BM25×0.4 + Vector×0.6 加权合并 |
| 4️⃣ **精排** | BGE-Reranker-v2-m3 | Cross-Encoder 交叉编码，逐对重排序 → Top-10 |
| 5️⃣ **LLM 排序** | DeepSeek V4 Flash | 语义理解排序 + ID/名称双重去重 |

## 📂 项目结构

```
resagent/
├── agents/                     # 🤖 5 个 Agent 模块
│   ├── parser/                 #   简历解析 (LLM → JSON)
│   ├── job_analyzer/           #   岗位分析 (JD → 需求+权重)
│   ├── matcher/                #   匹配评分 (逐候选人深度评估)
│   ├── bias_detector/          #   偏见检测 (五维公平性审计 · Pro + thinking)
│   └── report_generator/       #   报告生成 (LLM Flash 模式 · 缓存 + 模板降级)
│
├── agent_orchestration/        # 🔗 LangGraph 编排层
│   ├── graph.py                #   4 节点管线: job_analyzer→retriever→matcher→bias_detector
│   ├── state.py                #   TypedDict 状态定义 + SSE 事件发布
│   └── tools/                  #   检索工具
│       ├── bm25.py             #   BM25 全文检索 (jieba 分词)
│       ├── vector_search.py    #   Chroma 向量检索
│       └── calculator.py       #   评分计算工具
│
├── services/                   # ⚙️ 共享服务层
│   ├── llm_pool.py             #   DeepSeek API 调用池 (双模型路由 + Mock 降级)
│   ├── chroma_store.py         #   ChromaDB 持久化 (candidates + jobs 双集合)
│   ├── embedding.py            #   BGE-M3 Embedding (Sentence-Transformers)
│   ├── local_ml.py             #   BGE-Reranker-v2-m3 交叉编码重排序
│   ├── pdf_parser.py           #   文档解析 (PDF/DOCX → 文本)
│   └── cache_service.py        #   缓存服务 (diskcache)
│
├── api/                        # 🌐 FastAPI 路由层
│   ├── main.py                 #   应用入口 (CORS / 生命周期 / 健康检查)
│   ├── routes/
│   │   ├── jobs.py             #   CRUD: 职位管理
│   │   ├── resumes.py          #   CRUD: 简历上传 + LLM 解析
│   │   ├── screening.py        #   筛选任务 + SSE 流式进度
│   │   └── reports.py          #   报告生成 (Agent Flash 模式) + 导出
│   └── schemas/                #   Pydantic 请求/响应模型
│
├── models/                     # 🗃️ SQLAlchemy ORM 模型
│   ├── base.py                 #   引擎 / 会话 / Base 基类
│   ├── candidate.py            #   候选人
│   ├── job.py                  #   职位
│   ├── screening_task.py       #   筛选任务
│   ├── match_result.py         #   匹配结果 (持久化)
│   └── bias_report.py          #   偏见报告 (持久化)
│
├── frontend/                   # 🎨 Vue 3 + Nuxt 3
│   └── package.json            #   Nuxt 3 + Element Plus + Pinia
│
├── scripts/                    # 🔧 工具脚本
│   ├── check_env.py            #   环境检查
│   ├── init_db.py              #   建表
│   ├── seed_data.py            #   示例数据填充
│   └── demo_results.py         #   演示结果
│
├── tests/                      # ✅ 测试
│   ├── unit/                   #   单元测试 (pdf_parser / schemas / calculator)
│   └── integration/            #   集成测试 (agent_pipeline)
│
├── data/                       # 💾 SQLite + Chroma 持久化
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .env.example
├── requirements.txt
└── pyproject.toml
```

## 📡 SSE 实时进度

筛选任务通过 Server-Sent Events 实时推送管线进度，
前端通过 `EventSource` 原生接收，完全替代传统轮询：

```
GET /api/screening/{task_id}/stream

event: workflow_start    →  任务开始
event: node_update       →  job_analyzer / retriever / matcher / bias_detector 各阶段进度
event: workflow_complete →  最终结果 (候选人排名 + 检索指标)
event: workflow_error    →  异常信息
event: __done__          →  流结束哨兵，前端自动断开连接
```

## 🔌 API 概览

| 端点 | 方法 | 说明 |
|:-----|:-----|:-----|
| `/health` | GET | 健康检查 |
| `/api/stats` | GET | 首页仪表盘统计 |
| `/api/jobs/` | CRUD | 职位管理 |
| `/api/resumes/` | CRUD | 简历上传 + 解析 |
| `/api/screening/run` | POST | 启动筛选任务 |
| `/api/screening/{id}/stream` | GET | SSE 实时进度流 |
| `/api/screening/{id}/results` | GET | 筛选结果 + 匹配详情 |
| `/api/reports/` | GET | 报告查询 |
| `/api/screening/{id}/approve` | POST | 人工确认 (HITL · 规划中) |

## 🧪 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-----|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 (未设置自动 Mock 降级) | — |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite:///./data/resagent.db` |
| `CHROMA_PERSIST_DIR` | ChromaDB 持久化目录 | `./data/chroma` |
| `MOCK_LLM` | 强制 Mock 模式 (`true` 关闭时可离线测试) | `false` |
| `HF_ENDPOINT` | HuggingFace 镜像 (国内加速) | `https://hf-mirror.com` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
