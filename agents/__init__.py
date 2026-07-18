"""
ResAgent — 多智能体简历筛选系统（Multi-Agent Resume Screening System）.

该包包含五个核心 Agent，按工作流管线顺序排列：
  - Resume Parser Agent:      从非结构化的简历文本中提取结构化 JSON 数据并生成向量嵌入
  - Job Analyzer Agent:       从职位描述中提取结构化技能需求与权重
  - Candidate-Job Matcher:    执行四层匹配策略（精确匹配 + 语义匹配 + 可迁移匹配 + 维度评分）
  - Bias Detector Agent:      对匹配结果进行五维度公平性审计（性别、年龄、学历、地域、经验描述）
  - Report Generator Agent:   汇总所有阶段输出，生成 Markdown 格式的综合评估报告
"""
