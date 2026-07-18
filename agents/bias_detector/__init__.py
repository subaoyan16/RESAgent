"""
bias_detector 包初始化模块。

导出 run 函数，供编排层直接调用以执行偏差检测任务。
"""

from .agent import run

__all__ = ["run"]
