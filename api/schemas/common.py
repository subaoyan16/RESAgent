"""
模块: 通用 Pydantic 数据模型
定义健康检查、错误响应、分页参数、分页响应和通用消息等跨模块复用的数据结构。
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional
from datetime import datetime


class HealthCheck(BaseModel):
    """健康检查响应模型 — 用于 /health 端点返回服务状态"""
    status: str = "ok"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """错误响应模型 — 统一 API 错误返回格式"""
    detail: str
    error_code: Optional[str] = None


class PaginationParams(BaseModel):
    """分页参数模型 — 请求中的分页查询参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型 — 泛型，可包装任意类型的列表数据"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    """通用消息响应模型 — 用于操作成功后的简单消息返回"""
    message: str
