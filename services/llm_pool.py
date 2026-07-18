"""
LLM 调用池 — DeepSeek API 统一调用层，支持 Mock 模式

提供单例 LLMPool，通过 OpenAI 兼容接口调用 DeepSeek 端点，
无 API Key 时自动降级为模拟响应，方便离线测试。

双模型路由:
  - deepseek-v4-pro:   深度推理（matching / scoring / bias_detection）
  - deepseek-v4-flash: 高吞吐（parsing / analysis / report）
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock 响应数据 — 模拟 DeepSeek API 的返回结果
# 每个 key 对应一种任务场景（简历解析、匹配、偏见检测等）
# ---------------------------------------------------------------------------

_MOCK_RESPONSES: dict[str, str] = {
    "parsing": json.dumps(
        {
            "name": "\u5f20\u4f1f",
            "email": "zhangwei@example.com",
            "phone": "138-0000-0000",
            "skills": [
                {"name": "Python", "level": "expert", "years": 6, "category": "programming_language"},
                {"name": "TensorFlow", "level": "expert", "years": 4, "category": "ai_ml"},
                {"name": "PyTorch", "level": "intermediate", "years": 3, "category": "ai_ml"},
                {"name": "NLP", "level": "intermediate", "years": 2, "category": "ai_ml"},
                {"name": "Kubernetes", "level": "intermediate", "years": 3, "category": "devops"},
            ],
            "experience": [
                {
                    "company": "\u5b57\u8282\u8df3\u52a8",
                    "role": "\u9ad8\u7ea7\u7b97\u6cd5\u5de5\u7a0b\u5e08",
                    "duration": "2020-06 \u2014 2024-08",
                    "highlights": [
                        "\u642d\u5efa\u5927\u89c4\u6a21\u63a8\u8350\u7cfb\u7edf\uff0c\u65e5\u6d3b\u7528\u6237\u8d85 2 \u4ebf",
                        "\u4f18\u5316 CTR \u9884\u4f30\u6a21\u578b\uff0cAUC \u63d0\u5347 3.2%",
                    ],
                },
                {
                    "company": "\u963f\u91cc\u5df4\u5df4",
                    "role": "\u7b97\u6cd5\u5de5\u7a0b\u5e08",
                    "duration": "2017-09 \u2014 2020-05",
                    "highlights": ["\u5f00\u53d1\u667a\u80fd\u5ba2\u670d NLP \u7ba1\u7ebf", "\u5b9e\u4f53\u8bc6\u522b F1 \u8fbe 0.94"],
                },
            ],
            "education": {
                "degree": "\u7855\u58eb",
                "major": "\u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f",
                "school": "\u6e05\u534e\u5927\u5b66",
                "year": 2017,
            },
            "summary": "6 \u5e74\u673a\u5668\u5b66\u4e60\u4e0e NLP \u7ecf\u9a8c\uff0c\u719f\u6089\u63a8\u8350\u7cfb\u7edf\u4e0e\u5927\u89c4\u6a21\u5206\u5e03\u5f0f\u8bad\u7ec3\u3002",
        },
        ensure_ascii=False,
    ),
    "matching": json.dumps(
        {
            "dimension_scores": {
                "skill_match": 0.92,
                "experience_relevance": 0.85,
                "education": 0.80,
                "career_trajectory": 0.78,
                "other": 0.88,
            },
            "matched_skills": [
                {"skill": "Python", "requirement_level": "expert", "candidate_level": "expert", "match": 0.95},
                {"skill": "System Design", "requirement_level": "intermediate", "candidate_level": "intermediate", "match": 0.85},
            ],
            "unmatched_requirements": [
                {"skill": "Kubernetes", "importance": "nice_to_have", "gap_severity": "low"},
            ],
            "transferable_skills": [
                {"candidate_skill": "AWS", "mapped_to": "Cloud Infrastructure", "similarity": 0.82},
            ],
            "strengths": ["Python经验超过要求", "系统设计实战经验丰富"],
            "weaknesses": ["缺少K8s生产经验"],
            "recommendation_rationale": "候选人与岗位核心需求高度匹配，建议优先面试。",
        },
        ensure_ascii=False,
    ),
    "job_analysis": json.dumps(
        {
            "title": "高级后端工程师",
            "company": "示例科技有限公司",
            "requirements": {
                "hard": [
                    {"skill": "Python", "min_years": 5, "weight": 0.9, "category": "programming_language"},
                    {"skill": "分布式系统设计", "min_years": 3, "weight": 0.85, "category": "architecture"},
                    {"skill": "微服务架构", "min_years": 3, "weight": 0.80, "category": "architecture"},
                ],
                "nice_to_have": [
                    {"skill": "AWS", "weight": 0.3, "category": "cloud"},
                    {"skill": "Kubernetes", "weight": 0.25, "category": "devops"},
                    {"skill": "团队管理", "weight": 0.20, "category": "soft_skill"},
                ],
            },
            "education_requirement": {"min_degree": "bachelor", "preferred_majors": ["计算机科学", "软件工程"]},
            "soft_skills": ["沟通能力", "团队协作"],
            "industry_context": "企业服务/SaaS",
            "scoring_weights": {
                "skill_match": 0.45,
                "experience_relevance": 0.25,
                "education": 0.10,
                "career_trajectory": 0.10,
                "other": 0.10,
            },
        },
        ensure_ascii=False,
    ),
    "analysis": json.dumps(
        {
            "summary": "\u5019\u9009\u4eba\u6574\u4f53\u5b9e\u529b\u4f18\u79c0\uff0c\u6280\u672f\u6808\u4e0e\u5c97\u4f4d\u8981\u6c42\u9ad8\u5ea6\u543b\u5408\u3002",
            "risk_flags": [],
            "recommendation": "\u5b89\u6392\u6280\u672f\u9762\u8bd5",
            "suggested_interview_topics": [
                "\u63a8\u8350\u7cfb\u7edf\u53ec\u56de/\u6392\u5e8f\u67b6\u6784",
                "\u5927\u89c4\u6a21\u7279\u5f81\u5de5\u7a0b\u5b9e\u8df5",
                "\u6a21\u578b\u5728\u7ebf\u670d\u52a1\u4f18\u5316",
            ],
        },
        ensure_ascii=False,
    ),
    "report": (
        "# \u5019\u9009\u4eba\u8bc4\u4f30\u62a5\u544a\n\n"
        "## \u57fa\u672c\u4fe1\u606f\n- \u59d3\u540d\uff1a\u5f20\u4f1f\n- \u5f53\u524d\u516c\u53f8\uff1a\u5b57\u8282\u8df3\u52a8\n- \u7ecf\u9a8c\u5e74\u9650\uff1a6 \u5e74\n\n"
        "## \u6280\u672f\u80fd\u529b\n\u5019\u9009\u4eba\u5177\u5907\u624e\u5b9e\u7684\u673a\u5668\u5b66\u4e60\u57fa\u7840\u548c\u4e30\u5bcc\u7684\u5de5\u7a0b\u843d\u5730\u7ecf\u9a8c\u3002\n\n"
        "## \u5339\u914d\u7ed3\u8bba\n**\u7efc\u5408\u8bc4\u5206\uff1a87.5/100** \u2014 \u63a8\u8350\u8fdb\u5165\u4e0b\u4e00\u8f6e\u3002\n"
    ),
    "scoring": json.dumps(
        {
            "score": 87.5,
            "breakdown": {
                "technical": 92,
                "experience": 85,
                "culture": 78,
                "communication": 80,
            },
            "confidence": 0.89,
        },
        ensure_ascii=False,
    ),
    "bias_detection": json.dumps(
        {
            "bias_detected": False,
            "sensitive_attributes_used": [],
            "fairness_score": 0.97,
            "recommendation": "\u8be5\u8bc4\u4f30\u6d41\u7a0b\u672a\u53d1\u73b0\u660e\u663e\u504f\u89c1\u3002",
        },
        ensure_ascii=False,
    ),
}


def _mock_response(messages: list[dict[str, str]]) -> str:
    """根据最后一条用户消息的关键词，生成对应的 Mock 响应

    按优先级匹配:
      parsing(简历解析) > matching(匹配) > bias(偏见) > report(报告) > scoring(评分)

    Parameters
    ----------
    messages : list[dict]
        OpenAI 格式的消息列表。

    Returns
    -------
    str
        对应的 Mock 响应 JSON 字符串。
    """
    if not messages:
        return _MOCK_RESPONSES["analysis"]

    # 从后往前搜索最后一条用户消息
    last_content = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_content = (m.get("content") or "").lower()
            break

    # 关键词路由 — matching > job_analysis > parsing > bias > report > scoring
    if any(kw in last_content for kw in ("匹配", "match", "scor", "请对以下候选")):
        return _MOCK_RESPONSES["matching"]
    if any(kw in last_content for kw in ("analyze", "description", "jd", "job", "岗位", "职位", "requirement", "需求")):
        return _MOCK_RESPONSES["job_analysis"]
    if any(kw in last_content for kw in ("简历", "resume", "pars", "解析")):
        return _MOCK_RESPONSES["parsing"]
    if any(kw in last_content for kw in ("偏见", "bias", "公平")):
        return _MOCK_RESPONSES["bias_detection"]
    if any(kw in last_content for kw in ("报告", "report", "评估")):
        return _MOCK_RESPONSES["report"]
    if any(kw in last_content for kw in ("scor", "评分", "打分")):
        return _MOCK_RESPONSES["scoring"]

    # 无关键词匹配时默认返回 analysis
    return _MOCK_RESPONSES["analysis"]


# ---------------------------------------------------------------------------
# LLM Pool
# ---------------------------------------------------------------------------


class LLMPool:
    """DeepSeek API 调用池，支持双模型路由与 Mock 降级

    核心职责:
    - 双模型路由: Pro(深度推理) / Flash(高吞吐)
    - thinking 模式: 开启后模型输出推理链
    - 自动重试: 网络波动时最多重试 3 次（指数退避）
    - Mock 模式: 无 API Key 时返回模拟响应
    """

    def __init__(self, mock: bool = False) -> None:
        """初始化 LLM 调用池

        优先读取 DEEPSEEK_API_KEY 环境变量；若未设置则自动切换到 Mock 模式。

        Parameters
        ----------
        mock : bool
            是否强制启用 Mock 模式。也可通过环境变量 MOCK_LLM=1/true/yes 触发。
        """
        # 检测环境变量 MOCK_LLM，允许通过环境变量强制 Mock 模式
        self.mock = mock or os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes")
        self._client: AsyncOpenAI | None = None

        if not self.mock:
            # 从环境变量读取 DeepSeek API 配置
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            if not api_key:
                # API Key 未配置 -> 自动降级为 Mock 模式
                logger.warning("DEEPSEEK_API_KEY not set -- falling back to mock mode")
                self.mock = True
            else:
                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),          # 最多重试 3 次
        wait=wait_exponential(multiplier=1, min=1, max=10),  # 指数退避: 1s -> 2s -> 4s
        retry=retry_if_exception_type((TimeoutError, ConnectionError, IOError)),  # 仅网络类异常触发重试
        reraise=True,
    )
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        thinking: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str:
        """发送聊天补全请求

        Parameters
        ----------
        model : str
            模型标识符（如 "deepseek-v4-flash"、"deepseek-v4-pro"）。
        messages : list[dict]
            OpenAI 格式的消息列表。
        thinking : bool
            是否启用扩展思考模式（DeepSeek R1 风格），开启后模型输出推理链。
        temperature : float
            采样温度 (0.0-1.0)，值越低输出越确定。
        max_tokens : int
            最大输出 Token 数。

        Returns
        -------
        str
            模型返回的文本内容。
        """
        # Mock 模式：直接返回模拟响应，不发起网络请求
        if self.mock:
            logger.debug("Mock LLM response for %d messages", len(messages))
            return _mock_response(messages)

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # thinking 模式通过 extra_body 传递，DeepSeek 原生支持
        if thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        response = await self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
        msg = response.choices[0].message
        usage = response.usage
        if not msg.content:
            finish = response.choices[0].finish_reason
            raise RuntimeError(
                f"LLM 返回空内容 (model={model}, finish_reason={finish}, "
                f"prompt_tokens={usage.prompt_tokens if usage else '?'}, "
                f"completion_tokens={usage.completion_tokens if usage else '?'}, "
                f"max_tokens={max_tokens})"
            )
        return msg.content

    @staticmethod
    def get_model_for_task(task: str) -> str:
        """根据任务类型返回推荐的模型名称

        Parameters
        ----------
        task : str
            任务类型标识（parsing / analysis / report / matching / scoring / bias_detection）。

        Returns
        -------
        str
            DeepSeek 模型名称。
        """
        task_lower = task.lower().strip()
        # parsing / analysis / report 使用 Flash 模型（高吞吐，性价比高）
        if task_lower in ("parsing", "analysis", "report"):
            return "deepseek-v4-flash"
        # matching / scoring / bias_detection 使用 Pro 模型（深度推理，结果更准确）
        if task_lower in ("matching", "scoring", "bias_detection"):
            return "deepseek-v4-pro"
        # 默认使用经济的 Flash 模型
        return "deepseek-v4-flash"

    @staticmethod
    def needs_thinking(task: str) -> bool:
        """判断指定任务是否需要启用 thinking（扩展思考）模式

        Parameters
        ----------
        task : str
            任务类型标识。

        Returns
        -------
        bool
            需要 thinking 模式返回 True。
        """
        return task.lower().strip() in ("matching", "scoring", "bias_detection")


# 模块级单例 — 自动读取 MOCK_LLM 环境变量
_mock_env = os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes")
llm_pool = LLMPool(mock=_mock_env)
