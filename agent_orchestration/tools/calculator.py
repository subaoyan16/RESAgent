"""候选人-职位匹配的分数计算与推荐决策工具。

提供三个核心函数，构成匹配 Agent 的后处理层：
  - calculate_weighted_score:  按维度权重计算加权综合评分
  - determine_recommendation:  根据综合分数和差距情况输出推荐等级
  - calculate_match_score:     使用自定义权重配置计算最终匹配分
"""


def calculate_weighted_score(
    skill_match: float,
    experience_relevance: float,
    education: float,
    career_trajectory: float,
    weights: dict | None = None,
) -> dict:
    """按维度权重计算加权综合评分。

    将四个评分维度与对应权重相乘后求和，得到 overall_score（0-1）。
    如果权重总和不为 1.0，则会自动归一化以避免分数偏移。

    Args:
        skill_match: 技能匹配分数（0-1）
        experience_relevance: 经验相关性分数（0-1）
        education: 学历匹配分数（0-1）
        career_trajectory: 职业轨迹分数（0-1）
        weights: 各维度权重字典，默认使用标准权重配置

    Returns:
        包含 overall_score、dimension_scores 和 weights_used 的字典
    """
    if weights is None:
        weights = {
            "skill_match": 0.45,
            "experience_relevance": 0.25,
            "education": 0.10,
            "career_trajectory": 0.10,
            "other": 0.10,
        }
    overall = (
        skill_match * weights.get("skill_match", 0.45)
        + experience_relevance * weights.get("experience_relevance", 0.25)
        + education * weights.get("education", 0.10)
        + career_trajectory * weights.get("career_trajectory", 0.10)
    )
    total_weight = sum(weights.values())
    if total_weight > 0 and total_weight != 1.0:
        overall = overall / total_weight
    return {
        "overall_score": round(overall, 4),
        "dimension_scores": {
            "skill_match": round(skill_match, 4),
            "experience_relevance": round(experience_relevance, 4),
            "education": round(education, 4),
            "career_trajectory": round(career_trajectory, 4),
        },
        "weights_used": weights,
    }


def determine_recommendation(overall_score: float, has_gaps: bool = False) -> str:
    """根据综合分数和差距情况给出推荐结论。

    推荐等级划分：
      - strong_hire:      分数 >= 0.85 且无关键技能缺失
      - recommend:        分数 >= 0.70
      - hold:             分数 >= 0.50，需要进一步考察
      - not_recommended:  分数 < 0.50，不推荐进入下一轮

    Args:
        overall_score: 综合匹配分数（0-1）
        has_gaps: 是否存在关键技能缺失

    Returns:
        推荐等级字符串（strong_hire / recommend / hold / not_recommended）
    """
    if overall_score >= 0.85 and not has_gaps:
        return "strong_hire"
    elif overall_score >= 0.70:
        return "recommend"
    elif overall_score >= 0.50:
        return "hold"
    else:
        return "not_recommended"


def calculate_match_score(dimension_scores: dict, scoring_weights: dict) -> float:
    """根据自定义维度分数和权重计算综合匹配分。

    将每个维度的分数与对应权重相乘后求和，结果自动归一化（权重总和自动调整为 1.0），
    返回值保留 4 位小数。

    Args:
        dimension_scores: 各维度得分字典，如 {"skill_match": 0.9, "experience_relevance": 0.8}
        scoring_weights: 各维度权重字典，如 {"skill_match": 0.5, "experience_relevance": 0.5}

    Returns:
        归一化后的综合匹配分（0-1，保留 4 位小数）
    """
    total = 0.0
    weight_sum = 0.0
    for key, weight in scoring_weights.items():
        score = dimension_scores.get(key, 0.0)
        total += score * weight
        weight_sum += weight
    if weight_sum > 0:
        total = total / weight_sum
    return round(total, 4)
