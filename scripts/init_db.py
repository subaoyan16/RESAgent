#!/usr/bin/env python3
"""初始化 SQLite 数据库：创建所有 ORM 模型对应的数据表。

导入所有模型以确保它们在 Base.metadata 中注册，然后调用 init_db()
完成建表操作，最后列出已创建的表名供确认。
"""
import sys
import os

# 将项目根目录加入模块搜索路径，确保能够导入项目内部的包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.base import init_db, engine
# 导入所有模型模块，使其在 Base.metadata 中完成注册（仅靠副作用工作）
from models import *  # noqa: F401, F403


def main() -> None:
    """创建数据库表并在控制台输出结果摘要。"""
    print("📦 初始化数据库...")
    print(f"   Engine: {engine.url}")
    init_db()
    print("✅ 数据库表创建完成")

    # 使用 SQLAlchemy Inspector 获取当前所有表名并逐一打印
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    for t in tables:
        print(f"   - {t}")
    print(f"   共 {len(tables)} 张表")


if __name__ == "__main__":
    main()
