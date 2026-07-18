"""Pydantic Schema 校验单元测试。

验证候选人和职位创建请求的 Schema 校验逻辑，包括合法数据应通过、
非法邮箱应被拒绝等场景。
"""
import pytest
from datetime import datetime


class TestCandidateSchemas:
    """候选人 Schema 校验测试。"""

    def test_candidate_create_valid(self):
        """合法的候选人数据应能正常构造 CandidateCreate 实例。"""
        from api.schemas.candidate import CandidateCreate
        data = {
            "name": "张三",
            "email": "test@example.com",
            "years_of_experience": 5.0,
            "skills": [{"name": "Python", "level": "expert", "years": 5, "category": "programming_language"}]
        }
        c = CandidateCreate(**data)
        assert c.name == "张三"
        assert c.years_of_experience == 5.0

    def test_candidate_create_invalid_email(self):
        """传入非法邮箱地址时，应抛出 ValidationError。"""
        from api.schemas.candidate import CandidateCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CandidateCreate(name="Test", email="not-an-email", years_of_experience=1.0)


class TestJobSchemas:
    """职位 Schema 校验测试。"""

    def test_job_create_valid(self):
        """合法的职位数据应能正常构造 JobCreate 实例。"""
        from api.schemas.job import JobCreate
        data = {
            "title": "Senior Backend Engineer",
            "description": "A job description",
            "requirements": {
                "hard": [{"skill": "Python", "min_years": 5, "weight": 0.9, "category": "programming_language"}],
                "nice_to_have": []
            }
        }
        j = JobCreate(**data)
        assert j.title == "Senior Backend Engineer"
