#!/usr/bin/env python3
"""
GitHub 仓库数据分析系统
========================

功能:
  1. 通过 GitHub REST API 采集用户/组织的全部公开仓库数据
  2. 使用 Pandas 进行多维度数据分析
  3. 使用 Matplotlib 生成 6 张专业分析图表
  4. 输出完整的文字分析报告

使用方式:
  python main.py                       # 交互模式
  python main.py --user torvalds       # 指定 GitHub 用户名
  python main.py --user microsoft      # 指定组织名
  python main.py --user torvalds --token ghp_xxx  # 使用 Token 提升限流

依赖库 (>=4):
  - requests   : HTTP请求，数据采集
  - pandas     : 数据处理与分析
  - numpy      : 数值计算
  - matplotlib : 数据可视化

输出文件:
  - data/repos_{user}.csv            : 原始采集数据
  - output/01_top_stars.png          : Stars TOP10 柱状图
  - output/02_language_pie.png       : 编程语言分布饼图
  - output/03_stars_vs_forks.png     : Stars vs Forks 散点图
  - output/04_creation_timeline.png  : 仓库创建趋势图
  - output/05_stars_histogram.png    : Stars 分布直方图
  - output/06_language_stars.png     : 语言平均星数排行
  - output/analysis_report.txt       : 文字分析报告
"""

import argparse
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import pandas as pd

from github_api import GitHubAPI, resolve_token
from analyze import GitHubAnalyzer
from visualize import GitHubVisualizer
from pdf_export import export_pdf


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

KNOWN_USERS = {
    "1": {"user": "torvalds", "name": "Linus Torvalds (Linux 之父)"},
    "2": {"user": "microsoft", "name": "Microsoft"},
    "3": {"user": "google", "name": "Google"},
    "4": {"user": "facebook", "name": "Meta / Facebook"},
    "5": {"user": "TheAlgorithms", "name": "The Algorithms (算法集合)"},
}


def collect_data(user: str, token: str, max_repos: int = 200) -> pd.DataFrame:
    """采集 GitHub 仓库数据并保存为 CSV。"""
    csv_path = os.path.join(DATA_DIR, f"repos_{user}.csv")

    print(f"\n{'='*50}")
    print(f"  正在连接 GitHub API 获取 {user} 的仓库数据...")
    print(f"{'='*50}")

    api = GitHubAPI(token=token)

    try:
        info = api.get_user_info(user)
        print(f"  名称: {info.get('name', user)}")
        print(f"  公开仓库: {info.get('public_repos', '?')}")
        print(f"  粉丝数: {info.get('followers', 0):,}")
    except Exception as e:
        print(f"  [WARN] 获取用户信息失败: {e}")

    repos = api.collect_repo_data(user, max_repos=max_repos)

    if not repos:
        if os.path.exists(csv_path):
            print(f"\n  发现缓存文件: {csv_path}")
            ans = input("  是否使用缓存数据继续分析? [Y/n]: ").strip().lower()
            if ans != "n":
                df = pd.read_csv(csv_path, encoding="utf-8-sig")
                print(f"  已加载缓存数据: {len(df)} 条记录")
                return df
        print("  [FAIL] 未获取到任何仓库数据，请检查用户名是否正确")
        return pd.DataFrame()

    df = pd.DataFrame(repos)
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n  原始数据已保存至: {csv_path}")
    print(f"  共 {len(df)} 条记录 ({len(df.columns)} 个字段)")

    return df


def run_analysis(df: pd.DataFrame) -> str:
    """执行数据分析并返回报告。"""
    print(f"\n{'='*50}")
    print(f"  数据分析中...")
    print(f"{'='*50}")

    analyzer = GitHubAnalyzer(df)
    stats = analyzer.basic_stats()
    print("\n  [基础统计]")
    for k, v in stats.items():
        print(f"    {k}: {v}")

    report = analyzer.summary_report()
    report_path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  分析报告已保存至: {report_path}")
    return report


def run_visualization(df: pd.DataFrame) -> list[str]:
    """生成所有可视化图表。"""
    print(f"\n{'='*50}")
    print(f"  生成可视化图表...")
    print(f"{'='*50}")

    viz = GitHubVisualizer(df, OUTPUT_DIR)
    paths = viz.generate_all()
    print(f"\n  共生成 {len(paths)} 张图表，保存至 {OUTPUT_DIR}/")
    return paths


def show_menu() -> str:
    """显示用户选择菜单。"""
    print("\n" + "=" * 50)
    print("  GitHub 仓库数据分析系统")
    print("=" * 50)
    print("\n  请选择分析目标:")
    for k, v in KNOWN_USERS.items():
        print(f"    [{k}] {v['name']}")
    print("    [0] 手动输入 GitHub 用户名")
    print("    [q] 退出")

    choice = input("\n  请输入选项: ").strip()
    return choice


def main() -> None:
    """主入口。"""
    parser = argparse.ArgumentParser(description="GitHub 仓库数据分析系统")
    parser.add_argument("--user", type=str, default=None, help="GitHub 用户名或组织名")
    parser.add_argument("--token", type=str, default="", help="GitHub Token (也可通过环境变量 GITHUB_TOKEN 设置)")
    parser.add_argument("--max-repos", type=int, default=200, help="最大仓库数(默认200)")
    args = parser.parse_args()

    # Resolve token: CLI arg > env var GITHUB_TOKEN
    args.token = resolve_token(args.token)
    if args.token:
        print("  ✅ 已配置 GitHub Token（限流 5000次/小时）")
    else:
        print("  ⚠️  未配置 Token（限流 60次/小时），建议设置环境变量 GITHUB_TOKEN")

    user = args.user
    if user is None:
        while True:
            choice = show_menu()
            if choice.lower() == "q":
                print("  已退出。")
                return
            elif choice == "0":
                user = input("  请输入 GitHub 用户名: ").strip()
                if user:
                    break
                print("  [FAIL] 请输入有效的用户名")
            elif choice in KNOWN_USERS:
                user = KNOWN_USERS[choice]["user"]
                break
            else:
                print("  [FAIL] 无效选项，请重新选择")

    csv_path = os.path.join(DATA_DIR, f"repos_{user}.csv")
    df = pd.DataFrame()

    if os.path.exists(csv_path):
        print(f"\n  发现已有数据文件: repos_{user}.csv")
        print(f"  文件大小: {os.path.getsize(csv_path) / 1024:.1f} KB")
        ans = input("  是否使用已有数据跳过采集? [Y/n]: ").strip().lower()
        if ans != "n":
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            print(f"  已加载 {len(df)} 条记录")

    if df.empty:
        df = collect_data(user, args.token, max_repos=args.max_repos)

    if df.empty:
        print("\n[FAIL] 无数据可分析，程序终止。")
        return

    report = run_analysis(df)
    print("\n" + report)
    paths = run_visualization(df)

    # 生成 PDF 报告
    analyzer = GitHubAnalyzer(df)
    stats = analyzer.basic_stats()
    pdf_path = export_pdf(user, stats, report, paths, OUTPUT_DIR)
    print(f"\n  PDF 报告已生成: {pdf_path}")

    print(f"\n{'='*50}")
    print(f"  分析完成!")
    print(f"  - 数据文件: {DATA_DIR}/repos_{user}.csv")
    print(f"  - 分析报告: {OUTPUT_DIR}/analysis_report.txt")
    print(f"  - PDF 报告: {pdf_path}")
    print(f"  - 图表文件: {OUTPUT_DIR}/ (共{len(paths)}张)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
