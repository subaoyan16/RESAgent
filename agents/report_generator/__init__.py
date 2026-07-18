"""
report_generator 包初始化模块。

导出 run 函数，供编排层直接调用以生成候选人评估报告。
"""

from .agent import run

__all__ = ["run"]
