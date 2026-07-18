#!/usr/bin/env python3
"""启动前检查：验证应用程序启动所需的关键环境变量是否存在。

扫描 .env 文件并将变量加载到 os.environ 中，然后检查必需的变量（如
DEEPSEEK_API_KEY）是否已设置，并为可选的变量设定默认值。
"""
import os
import sys

# 加载 .env 文件中的环境变量（如果存在）
from pathlib import Path
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释行，只处理包含 "=" 的有效行
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                # 不覆盖已在环境中存在的变量
                if key not in os.environ:
                    os.environ[key] = value

# 必须设置的环境变量列表，缺少会导致程序无法正常运行
REQUIRED = {
    "DEEPSEEK_API_KEY": "DeepSeek API 密钥，从 https://platform.deepseek.com/api_keys 获取",
}

# 可选的环境变量及其默认值
OPTIONAL = {
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "LANGCHAIN_TRACING_V2": "false",
    "DATABASE_URL": "sqlite:///./data/resagent.db",
    "CHROMA_PERSIST_DIR": "./data/chroma",
}


def check() -> bool:
    """执行环境检查并设置变量默认值。

    依次检查必需变量是否缺失、是否启用 MOCK_LLM 模式（绕过 API Key 检查）、
    并为可选变量注入默认值。

    Returns:
        所有必需变量均已就绪（或处于 Mock 模式）时返回 True，否则返回 False。
    """
    all_ok = True

    # 1. 收集所有缺失的必需环境变量
    missing = []
    for key, desc in REQUIRED.items():
        if not os.getenv(key):
            missing.append(f"  - {key}: {desc}")
            all_ok = False

    # 如果存在缺失项，打印警告信息
    if missing:
        print("❌ 缺少必要的环境变量：")
        for m in missing:
            print(m)
        print()

    # 2. 检查 MOCK_LLM 模式 —— 启用后即使没有 API Key 也能正常运行
    if os.getenv("MOCK_LLM", "").lower() == "true":
        print("⚠️  MOCK_LLM=true，将使用模拟 LLM 响应（无需 API Key）")
        # Mock 模式下撤销 API Key 缺失导致的失败状态
        all_ok = True

    # 3. 为未设置的可选变量填充默认值
    for key, default in OPTIONAL.items():
        if not os.getenv(key):
            os.environ[key] = default

    # 4. 输出最终检查结果及当前生效配置
    if all_ok:
        print("✅ 环境变量检查通过")
        print(f"   LLM: {'Mock模式' if os.getenv('MOCK_LLM')=='true' else 'DeepSeek API'}")
        print(f"   数据库: {os.getenv('DATABASE_URL', 'N/A')}")
        print(f"   Chroma: {os.getenv('CHROMA_PERSIST_DIR', 'N/A')}")
        if os.getenv("LANGCHAIN_TRACING_V2") == "true":
            print(f"   LangSmith: 已启用 (project: {os.getenv('LANGCHAIN_PROJECT', 'resagent')})")
    else:
        print("\n请复制 .env.example 为 .env 并填入正确的值。")
        print("或设置 MOCK_LLM=true 使用模拟模式启动。")

    return all_ok


if __name__ == "__main__":
    ok = check()
    sys.exit(0 if ok else 1)
