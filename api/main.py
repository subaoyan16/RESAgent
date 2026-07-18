"""
模块: FastAPI 应用程序入口
创建和配置 FastAPI 应用实例，注册路由、中间件，管理应用生命周期（启动/关闭）。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 应用生命周期管理 — 启动和关闭时的回调。

    **启动时**：加载 .env 文件、配置 Python 模块搜索路径、检查环境变量、
    初始化数据库表。

    **关闭时**：打印关闭日志。
    """
    # ── 启动阶段 ──────────────────────────────────────────────────────
    import os
    import sys

    # 优先加载 .env 文件（在其他导入之前），将环境变量注入 os.environ
    from pathlib import Path
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key not in os.environ:
                        os.environ[key] = value

    # 将项目根目录添加到 sys.path，确保所有内部导入（models、services、agents 等）能正确解析
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    # 检查运行环境（缺失 API 密钥等会发出警告）
    from scripts.check_env import check
    check()

    # 初始化数据库表（若表不存在则自动创建）
    from models.base import init_db
    init_db()

    print("🚀 ResAgent API 启动完成")
    yield
    # ── 关闭阶段 ───────────────────────────────────────────────────────
    print("👋 ResAgent API 关闭")


app = FastAPI(
    title="ResAgent API",
    description="多智能体简历筛选系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS 跨域配置 — 允许前端开发服务器访问
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],   # 允许所有 HTTP 方法
    allow_headers=["*"],   # 允许所有请求头
)

# ---------------------------------------------------------------------------
# 注册路由
# ---------------------------------------------------------------------------
from api.routes import jobs, resumes, screening, reports

app.include_router(jobs.router, prefix="/api/jobs", tags=["职位管理"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["简历管理"])
app.include_router(screening.router, prefix="/api/screening", tags=["筛选任务"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告管理"])


# ---------------------------------------------------------------------------
# 健康检查端点
# ---------------------------------------------------------------------------
@app.get("/health", tags=["系统"])
async def health_check():
    """简单的存活探针 — 返回服务运行状态和版本信息。

    Returns:
        HealthCheck 模型（status、version、timestamp）
    """
    from api.schemas.common import HealthCheck
    return HealthCheck()


@app.get("/api/stats", tags=["系统"])
async def get_stats():
    """返回首页仪表盘所需的统计数据"""
    from models.job import Job
    from models.candidate import Candidate
    from models.screening_task import ScreeningTask
    from models.base import SessionLocal
    db = SessionLocal()
    try:
        total_jobs = db.query(Job).filter(Job.status != "closed").count()
        total_candidates = db.query(Candidate).filter(Candidate.name != None, Candidate.name != '').count()
        completed_tasks = db.query(ScreeningTask).filter(ScreeningTask.status == "completed").count()
        return {
            "totalJobs": total_jobs,
            "totalCandidates": total_candidates,
            "completedTasks": completed_tasks,
        }
    finally:
        db.close()
