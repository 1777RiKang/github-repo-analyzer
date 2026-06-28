#!/usr/bin/env python3
"""
GitHub 仓库数据分析系统 — 一键启动 Web 界面
双击此文件或执行 python run_web.py 即可自动打开浏览器。
"""

import os
import sys
import subprocess


def main():
    # 定位 src 目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(project_root, "src")

    if not os.path.exists(os.path.join(src_dir, "app.py")):
        print("❌ 未找到 src/app.py，请确认项目结构完整")
        input("按 Enter 退出...")
        return

    # 检查 streamlit 是否安装
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("❌ 未安装 Streamlit，正在自动安装...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "streamlit"],
            stdout=subprocess.DEVNULL,
        )
        print("✅ Streamlit 安装完成\n")

    # 检查依赖
    requirements = os.path.join(project_root, "requirements.txt")
    if os.path.exists(requirements):
        try:
            import pandas, matplotlib, wordcloud  # noqa: F401
        except ImportError:
            print("📦 正在安装项目依赖...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", requirements],
                stdout=subprocess.DEVNULL,
            )
            print("✅ 依赖安装完成\n")

    print("=" * 50)
    print("  GitHub 仓库数据分析系统")
    print("  正在启动 Web 界面...")
    print("  浏览器将自动打开 http://localhost:8501")
    print("  关闭此窗口即可停止服务")
    print("=" * 50)

    # 切换到 src 目录并启动 streamlit
    os.chdir(src_dir)
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py"],
            cwd=src_dir,
        )
    except KeyboardInterrupt:
        print("\n服务已停止。")


if __name__ == "__main__":
    main()
