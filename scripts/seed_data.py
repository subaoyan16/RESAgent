#!/usr/bin/env python3
"""种子数据注入脚本：向数据库插入 10 份模拟简历和 5 个模拟职位（中文）。

提供 --reset 选项以在插入前清空 Candidates 和 Jobs 表，方便反复
测试数据库初始化和数据预览功能。
"""
import sys
import os
import json
import argparse

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.base import SessionLocal, init_db
from models.candidate import Candidate
from models.job import Job

# ======================== 模拟简历数据 ========================
MOCK_RESUMES = [
    {
        "name": "张三",
        "email": "zhangsan@example.com",
        "phone": "138****1234",
        "location": "北京",
        "years_of_experience": 7.5,
        "skills": [
            {"name": "Python", "level": "expert", "years": 7},
            {"name": "AWS", "level": "intermediate", "years": 4},
            {"name": "Docker", "level": "intermediate", "years": 3},
            {"name": "PostgreSQL", "level": "advanced", "years": 5},
        ],
        "education": [
            {"school": "清华大学", "degree": "master", "major": "计算机科学", "year": 2017}
        ],
        "summary": "7年+后端开发经验，擅长分布式系统设计和微服务架构，主导过日活百万级的后台系统重构。",
    },
    {
        "name": "李四",
        "email": "lisi@example.com",
        "phone": "139****5678",
        "location": "上海",
        "years_of_experience": 3.0,
        "skills": [
            {"name": "Java", "level": "advanced", "years": 3},
            {"name": "Spring Boot", "level": "advanced", "years": 3},
            {"name": "MySQL", "level": "intermediate", "years": 2},
            {"name": "Redis", "level": "intermediate", "years": 1.5},
        ],
        "education": [
            {"school": "上海交通大学", "degree": "bachelor", "major": "软件工程", "year": 2022}
        ],
        "summary": "3年Java开发经验，熟悉微服务架构和Spring全家桶，参与过电商平台订单系统的开发。",
    },
    {
        "name": "王五",
        "email": "wangwu@example.com",
        "phone": "137****9012",
        "location": "深圳",
        "years_of_experience": 10.0,
        "skills": [
            {"name": "Go", "level": "expert", "years": 8},
            {"name": "Kubernetes", "level": "expert", "years": 5},
            {"name": "gRPC", "level": "advanced", "years": 4},
            {"name": "MongoDB", "level": "advanced", "years": 6},
        ],
        "education": [
            {"school": "浙江大学", "degree": "master", "major": "计算机科学与技术", "year": 2014}
        ],
        "summary": "10年后端与基础架构经验，专注于高并发系统和云原生技术，主导过公司核心服务从单体到微服务的迁移。",
    },
    {
        "name": "赵六",
        "email": "zhaoliu@example.com",
        "phone": "136****3456",
        "location": "北京",
        "years_of_experience": 1.5,
        "skills": [
            {"name": "React", "level": "intermediate", "years": 1.5},
            {"name": "TypeScript", "level": "intermediate", "years": 1},
            {"name": "JavaScript", "level": "advanced", "years": 2},
            {"name": "CSS", "level": "intermediate", "years": 1.5},
        ],
        "education": [
            {"school": "北京理工大学", "degree": "bachelor", "major": "信息管理与信息系统", "year": 2024}
        ],
        "summary": "1.5年前端开发经验，熟悉React生态和TypeScript，参与过中后台管理系统的前端开发。",
    },
    {
        "name": "陈七",
        "email": "chenqi@example.com",
        "phone": "135****7890",
        "location": "杭州",
        "years_of_experience": 5.0,
        "skills": [
            {"name": "Python", "level": "advanced", "years": 5},
            {"name": "PyTorch", "level": "advanced", "years": 3},
            {"name": "TensorFlow", "level": "intermediate", "years": 2},
            {"name": "NLP", "level": "intermediate", "years": 3},
            {"name": "MLOps", "level": "intermediate", "years": 1},
        ],
        "education": [
            {"school": "中国科学技术大学", "degree": "phd", "major": "人工智能", "year": 2019}
        ],
        "summary": "5年机器学习研发经验，博士研究方向为自然语言处理，主导过智能客服和推荐系统的算法迭代。",
    },
    {
        "name": "刘八",
        "email": "liuba@example.com",
        "phone": "134****2345",
        "location": "上海",
        "years_of_experience": 8.0,
        "skills": [
            {"name": "Kubernetes", "level": "expert", "years": 6},
            {"name": "AWS", "level": "expert", "years": 7},
            {"name": "Terraform", "level": "advanced", "years": 4},
            {"name": "CI/CD", "level": "expert", "years": 6},
            {"name": "Linux", "level": "expert", "years": 8},
        ],
        "education": [
            {"school": "华中科技大学", "degree": "bachelor", "major": "网络工程", "year": 2016}
        ],
        "summary": "8年DevOps/SRE经验，主导过日调用量十亿级服务的云原生架构和运维体系建设。",
    },
    {
        "name": "孙九",
        "email": "sunjiu@example.com",
        "phone": "133****6789",
        "location": "成都",
        "years_of_experience": 12.0,
        "skills": [
            {"name": "Java", "level": "expert", "years": 12},
            {"name": "Spark", "level": "expert", "years": 6},
            {"name": "Flink", "level": "advanced", "years": 4},
            {"name": "Kafka", "level": "expert", "years": 7},
            {"name": "Hadoop", "level": "advanced", "years": 5},
        ],
        "education": [
            {"school": "哈尔滨工业大学", "degree": "master", "major": "计算机系统结构", "year": 2014}
        ],
        "summary": "12年数据工程经验，专注大数据平台和数据管道建设，主导过PB级数据仓库的规划和实施。",
    },
    {
        "name": "周十",
        "email": "zhoushi@example.com",
        "phone": "132****0123",
        "location": "广州",
        "years_of_experience": 4.0,
        "skills": [
            {"name": "Vue", "level": "advanced", "years": 4},
            {"name": "React", "level": "intermediate", "years": 2},
            {"name": "Node.js", "level": "advanced", "years": 3},
            {"name": "TypeScript", "level": "advanced", "years": 3},
            {"name": "Webpack", "level": "intermediate", "years": 3},
        ],
        "education": [
            {"school": "中山大学", "degree": "bachelor", "major": "计算机科学与技术", "year": 2021}
        ],
        "summary": "4年前端全栈开发经验，精通Vue和React两大框架，有从零搭建前端工程化体系的经验。",
    },
    {
        "name": "吴一",
        "email": "wuyi@example.com",
        "phone": "131****4567",
        "location": "北京",
        "years_of_experience": 6.0,
        "skills": [
            {"name": "Python", "level": "advanced", "years": 6},
            {"name": "Rust", "level": "intermediate", "years": 1},
            {"name": "C++", "level": "advanced", "years": 4},
            {"name": "Linux Kernel", "level": "intermediate", "years": 2},
            {"name": "Performance Tuning", "level": "advanced", "years": 3},
        ],
        "education": [
            {"school": "北京大学", "degree": "master", "major": "计算机系统结构", "year": 2018}
        ],
        "summary": "6年系统软件开发经验，熟悉Python和C++，擅长性能分析和底层系统优化。",
    },
    {
        "name": "郑二",
        "email": "zheng@example.com",
        "phone": "130****8901",
        "location": "深圳",
        "years_of_experience": 2.0,
        "skills": [
            {"name": "Python", "level": "intermediate", "years": 2},
            {"name": "SQL", "level": "intermediate", "years": 2},
            {"name": "Tableau", "level": "intermediate", "years": 1},
            {"name": "A/B Testing", "level": "intermediate", "years": 1},
        ],
        "education": [
            {"school": "南京大学", "degree": "master", "major": "应用统计", "year": 2024}
        ],
        "summary": "2年数据分析经验，熟练使用Python进行数据分析和可视化，对用户增长有一定实践经验。",
    },
]

# ======================== 模拟职位数据 ========================
MOCK_JOBS = [
    {
        "title": "高级后端工程师",
        "company": "金融科技有限公司",
        "location": "北京",
        "department": "技术部-后端",
        "employment_type": "全职",
        "min_years": 5,
        "max_years": 10,
        "required_skills": [
            {"name": "Python", "level": "advanced"},
            {"name": "Go", "level": "intermediate"},
            {"name": "微服务架构", "level": "advanced"},
            {"name": "MySQL", "level": "advanced"},
            {"name": "Kafka", "level": "intermediate"},
        ],
        "description": "负责金融核心交易系统的后端架构设计与开发，保障系统的高可用性和数据一致性。",
        "education_required": "bachelor",
        "salary_range": "35K-55K",
    },
    {
        "title": "前端技术负责人",
        "company": "电商科技有限公司",
        "location": "上海",
        "department": "技术部-前端",
        "employment_type": "全职",
        "min_years": 5,
        "max_years": 10,
        "required_skills": [
            {"name": "React", "level": "expert"},
            {"name": "Vue", "level": "advanced"},
            {"name": "TypeScript", "level": "expert"},
            {"name": "Node.js", "level": "advanced"},
            {"name": "前端工程化", "level": "expert"},
        ],
        "description": "负责公司电商平台前端技术架构，带领10人前端团队，推进前端工程化和性能优化。",
        "education_required": "bachelor",
        "salary_range": "40K-65K",
    },
    {
        "title": "机器学习工程师",
        "company": "智能科技AI初创",
        "location": "杭州",
        "department": "算法部",
        "employment_type": "全职",
        "min_years": 3,
        "max_years": 8,
        "required_skills": [
            {"name": "Python", "level": "expert"},
            {"name": "PyTorch", "level": "advanced"},
            {"name": "TensorFlow", "level": "intermediate"},
            {"name": "NLP", "level": "advanced"},
            {"name": "MLOps", "level": "intermediate"},
        ],
        "description": "研发新一代智能对话系统和推荐算法，参与模型训练、评估和线上部署全流程。",
        "education_required": "master",
        "salary_range": "30K-50K",
    },
    {
        "title": "DevOps工程师",
        "company": "云服务SaaS公司",
        "location": "深圳",
        "department": "基础设施部",
        "employment_type": "全职",
        "min_years": 3,
        "max_years": 8,
        "required_skills": [
            {"name": "Kubernetes", "level": "advanced"},
            {"name": "AWS", "level": "advanced"},
            {"name": "Terraform", "level": "intermediate"},
            {"name": "CI/CD", "level": "advanced"},
            {"name": "Linux", "level": "expert"},
        ],
        "description": "负责SaaS平台的云基础设施建设和CI/CD流水线维护，推进基础设施即代码实践。",
        "education_required": "bachelor",
        "salary_range": "30K-50K",
    },
    {
        "title": "数据工程师",
        "company": "大数据科技公司",
        "location": "北京",
        "department": "数据平台部",
        "employment_type": "全职",
        "min_years": 3,
        "max_years": 8,
        "required_skills": [
            {"name": "Spark", "level": "advanced"},
            {"name": "Flink", "level": "intermediate"},
            {"name": "Kafka", "level": "advanced"},
            {"name": "Hadoop", "level": "advanced"},
            {"name": "SQL", "level": "expert"},
        ],
        "description": "设计和维护实时/离线数据管道，建设公司统一数据平台，支撑BI分析和算法特征工程。",
        "education_required": "bachelor",
        "salary_range": "30K-55K",
    },
]


def insert_data(session, reset: bool = False):
    """向数据库中插入所有模拟简历和职位数据。

    如果 reset 为 True，则先清空 Candidates 和 Jobs 两张表。

    Args:
        session: SQLAlchemy 数据库会话对象。
        reset: 是否在插入前先删除已有数据。

    Returns:
        (candidates_created, jobs_created) 的二元组，表示各自实际插入的记录数。
    """
    # 如果启用了 reset 模式，先清空两张表
    if reset:
        print("⚠️  --reset 标记已开启，删除已有数据...")
        session.query(Candidate).delete()
        session.query(Job).delete()
        session.commit()
        print("   已清空 Candidates 和 Jobs 表")

    # 逐条插入简历数据，将完整结构体以 JSON 形式存入 structured_data 字段
    candidates_created = 0
    for rd in MOCK_RESUMES:
        candidate = Candidate(
            name=rd["name"],
            email=rd["email"],
            structured_data=json.dumps(rd, ensure_ascii=False),
        )
        session.add(candidate)
        candidates_created += 1

    # 逐条插入职位数据，将完整结构体以 JSON 形式存入 requirements 字段
    jobs_created = 0
    for jd in MOCK_JOBS:
        job = Job(
            title=jd["title"],
            company=jd["company"],
            location=jd["location"],
            department=jd["department"],
            description=jd["description"],
            requirements=json.dumps(jd, ensure_ascii=False),
            is_active=True,
        )
        session.add(job)
        jobs_created += 1

    session.commit()
    return candidates_created, jobs_created


def main() -> None:
    """命令行入口：解析参数、初始化数据库、注入种子数据并在控制台输出摘要。"""
    parser = argparse.ArgumentParser(description="Seed mock data into ResAgent database")
    parser.add_argument("--reset", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()

    print("📦 注入种子数据...")
    init_db()
    db = SessionLocal()
    try:
        cand_count, job_count = insert_data(db, reset=args.reset)
        print(f"✅ 已插入 {cand_count} 个候选人")
        print(f"✅ 已插入 {job_count} 个职位")

        # 输出候选人列表预览（仅显示前三项技能）
        print()
        print("📋 候选人列表：")
        for rd in MOCK_RESUMES:
            skills_preview = ", ".join(s["name"] for s in rd["skills"][:3])
            print(f"   - {rd['name']} | {rd['location']} | {rd['years_of_experience']}年 | {skills_preview}")

        # 输出职位列表预览
        print()
        print("📋 职位列表：")
        for jd in MOCK_JOBS:
            print(f"   - {jd['title']} | {jd['company']} | {jd['location']}")

        print()
        print("✨ 种子数据注入完成")
    finally:
        # 确保会话被正确关闭，避免连接泄漏
        db.close()


if __name__ == "__main__":
    main()
