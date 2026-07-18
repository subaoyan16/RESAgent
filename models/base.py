"""
模块: 数据库基础配置
配置 SQLAlchemy 引擎、会话工厂和声明式基类，提供数据库初始化和依赖注入函数。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

# 数据库连接 URL — 优先从环境变量读取，默认使用本地 SQLite 文件
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/resagent.db")

# SQLite 不支持多线程并发访问，设置 check_same_thread=False 以允许 FastAPI 在多线程中使用
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False

# 创建全局引擎实例（echo=False 表示不打印 SQL 日志）
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
# 创建会话工厂，autocommit/autoflush 均关闭，由应用层控制事务
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类 — 所有 ORM 模型都继承自此类"""
    pass


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束后自动关闭。

    Yields:
        Session: SQLAlchemy 数据库会话实例
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库 — 根据所有 ORM 模型的定义创建不存在的表"""
    Base.metadata.create_all(bind=engine)
