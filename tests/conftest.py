"""ResAgent 测试套件的共享 Fixture 定义。

提供内存 SQLite 数据库、临时 Chroma 持久化目录、Mock LLM 模式以及
示例简历/职位文本等 pytest fixture，供各测试模块复用。
"""
import pytest
import os
import tempfile
import sys

# 将项目根目录加入模块搜索路径，确保测试时可以导入项目内部模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def test_db():
    """创建内存 SQLite 数据库供测试使用。

    会在每次请求该 fixture 的测试前创建一个全新的内存数据库，
    测试结束后销毁所有表，避免跨用例数据污染。
    """
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from models.base import init_db, engine
    init_db()
    yield
    # 清理：释放所有表以隔离不同测试用例
    from models.base import Base
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_chroma_dir():
    """创建临时 Chroma 持久化目录。

    使用 tempfile.TemporaryDirectory 自动管理目录生命周期，
    测试结束后该目录及其内容将被自动删除。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CHROMA_PERSIST_DIR"] = tmpdir
        yield tmpdir


@pytest.fixture
def mock_llm_response():
    """启用 Mock LLM 模式（无需真实 API Key）。

    在该 fixture 的作用域内将 MOCK_LLM 设为 "true"，测试结束后恢复
    为 "false"，确保不影响其他测试。
    """
    os.environ["MOCK_LLM"] = "true"
    yield
    os.environ["MOCK_LLM"] = "false"


@pytest.fixture
def sample_resume_text():
    """提供一份示例简历原始文本（中文），包含技能、工作经历和教育背景。"""
    return """张三 | Senior Software Engineer
Email: zhangsan@example.com | Phone: 138****1234 | Location: 北京
Experience: 7.5 years

SKILLS
Python (7年), Java (3年), AWS (4年), Kubernetes (3年), PostgreSQL (5年), System Design (4年)

WORK EXPERIENCE
阿里巴巴 | 高级后端工程师 | 2020.03 - present
- 设计并实现分布式交易系统，日处理订单量 1000万+
- 使用 Python + Go 重构核心支付模块，性能提升 40%
- 技术栈: Python, Go, AWS, Kubernetes, PostgreSQL

腾讯 | 后端工程师 | 2017.07 - 2020.02
- 负责微信小程序后端 API 开发
- 技术栈: Java, Spring Boot, MySQL, Redis

EDUCATION
清华大学 | 硕士 | 计算机科学 | 2017
北京大学 | 学士 | 软件工程 | 2015

CERTIFICATIONS
AWS Solutions Architect Professional

LANGUAGES
中文 (母语), English (fluent)
"""


@pytest.fixture
def sample_jd_text():
    """提供一份示例职位描述原始文本（中文），包含岗位要求、优先条件和学历要求。"""
    return """岗位: 高级后端工程师 (金融科技)
公司: 某头部金融科技公司

【必须要求】
- Python 5年以上开发经验
- 分布式系统设计 3年以上经验
- 熟悉金融行业合规要求

【优先考虑】
- Kubernetes 生产环境经验
- 有大模型应用开发经验者加分
- 团队管理经验 2年以上

【学历要求】
计算机相关专业硕士及以上
"""
