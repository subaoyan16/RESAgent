#!/usr/bin/env python3
"""基于磁盘的 LRU 缓存 — LLM 响应与嵌入向量的缓存层

使用 diskcache（生产环境）/ 内存字典（开发环境）实现 LRU 淘汰策略，
减少重复 API 调用和嵌入计算开销，提升响应速度。
"""
import os
import hashlib
import json

# diskcache 为可选依赖，缺失时自动降级为内存字典
try:
    import diskcache
    HAS_DISKCACHE = True
except ImportError:
    HAS_DISKCACHE = False


class CacheService:
    """基于磁盘的 LRU 缓存，带内存字典降级

    设计要点:
    - 生产环境: 使用 diskcache.Cache，支持 TTL 过期、LRU 淘汰、持久化
    - 开发/测试: diskcache 不可用时降级为 dict，无持久化但功能正常
    - 容量限制: 磁盘缓存上限 500MB，超出后自动淘汰最久未使用的条目
    - 确定性键: 通过 MD5 哈希生成固定长度的缓存键
    """

    def __init__(self, cache_dir: str = None):
        """初始化缓存服务

        Parameters
        ----------
        cache_dir : str | None
            缓存文件目录。默认为项目根目录下的 data/cache/。
        """
        if cache_dir is None:
            # 默认缓存路径: <项目根>/data/cache/
            cache_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "cache",
            )
        # 确保缓存目录存在，不存在则创建
        os.makedirs(cache_dir, exist_ok=True)
        self._cache_dir = cache_dir
        # 优先使用 diskcache（持久化 + LRU），否则使用内存字典
        if HAS_DISKCACHE:
            # 500MB 容量限制，超出后自动淘汰旧条目
            self._cache = diskcache.Cache(cache_dir, size_limit=500 * 1024 * 1024)
        else:
            # 降级: 使用简单内存字典（进程重启后缓存丢失）
            self._cache = {}

    def get(self, key: str):
        """根据键获取缓存值

        Parameters
        ----------
        key : str
            缓存键。

        Returns
        -------
        Any | None
            缓存的值。键不存在或发生异常时返回 None。
        """
        try:
            value = self._cache.get(key)
            return value
        except Exception:
            # 缓存读取异常时静默失败，不影响主流程
            return None

    def set(self, key: str, value, ttl: int = 3600):
        """存储缓存条目

        Parameters
        ----------
        key : str
            缓存键。
        value : Any
            要缓存的值。
        ttl : int
            生存时间（秒），默认 3600 秒（1 小时）。
            diskcache 模式下自动过期；内存模式下忽略。
        """
        try:
            if HAS_DISKCACHE:
                # diskcache 支持原生 TTL 过期
                self._cache.set(key, value, expire=ttl)
            else:
                # 内存模式直接赋值（无 TTL 支持）
                self._cache[key] = value
        except Exception:
            # 写入异常时静默失败，不影响主流程
            pass

    def invalidate(self, pattern: str = "*"):
        """使匹配模式的缓存条目失效

        Parameters
        ----------
        pattern : str
            glob 匹配模式（仅 diskcache 模式有效）。
            内存模式下忽略此参数，直接清空整个缓存。

        Returns
        -------
        int
            失效的条目数量。
        """
        if HAS_DISKCACHE:
            # diskcache 支持按 glob 模式选择性失效
            count = self._cache.evict(pattern)
            return count
        else:
            # 内存模式: 清空全部缓存
            count = len(self._cache)
            self._cache.clear()
            return count

    @staticmethod
    def make_key(*args) -> str:
        """根据传入参数生成确定性的 MD5 十六进制缓存键

        将多个参数用 "|" 连接后计算 MD5 哈希，确保相同参数产生相同键。

        Parameters
        ----------
        *args : Any
            构成缓存键的任意参数（如模型名、消息内容、温度等）。

        Returns
        -------
        str
            32 位 MD5 十六进制字符串。
        """
        raw = "|".join(str(a) for a in args)
        return hashlib.md5(raw.encode()).hexdigest()


# 模块级单例 — 全局共享 CacheService 实例
cache_service = CacheService()
