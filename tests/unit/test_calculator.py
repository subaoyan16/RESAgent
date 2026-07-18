"""评分计算工具单元测试。

测试加权评分和推荐决策逻辑，验证默认权重计算是否在预期范围内，
以及强推荐 / 不推荐两个边界条件下的决策结果。
"""
import pytest


class TestScoreCalculator:
    """评分计算器测试套件。"""

    def test_weighted_score_default_weights(self):
        """使用默认权重计算综合得分，结果应落在 (0.7, 0.8) 区间内。

        验证公式: skill_match(0.45) + experience_relevance(0.25) +
                  education(0.10) + career_trajectory(0.10) = 0.735
        """
        from agent_orchestration.tools.calculator import calculate_weighted_score
        result = calculate_weighted_score.invoke({
            "skill_match": 0.9, "experience_relevance": 0.8, "education": 0.7, "career_trajectory": 0.6
        })
        # 0.9*0.45 + 0.8*0.25 + 0.7*0.10 + 0.6*0.10 = 0.405 + 0.2 + 0.07 + 0.06 = 0.735
        data = result if isinstance(result, dict) else eval(str(result))
        overall = data.get("overall_score", data) if isinstance(data, dict) else data
        assert 0.7 < float(str(overall)) < 0.8

    def test_determine_recommendation_strong_hire(self):
        """综合得分 0.90 且无关键项缺失时，应返回 strong_hire 推荐。"""
        from agent_orchestration.tools.calculator import determine_recommendation
        result = determine_recommendation.invoke({"overall_score": 0.90, "has_gaps": False})
        assert "strong_hire" in str(result).lower() or "strong" in str(result).lower()

    def test_determine_recommendation_not_recommended(self):
        """综合得分 0.30 且有关键项缺失时，应返回 not_recommended 推荐。"""
        from agent_orchestration.tools.calculator import determine_recommendation
        result = determine_recommendation.invoke({"overall_score": 0.30, "has_gaps": True})
        assert "not_recommended" in str(result).lower() or "not" in str(result).lower()
