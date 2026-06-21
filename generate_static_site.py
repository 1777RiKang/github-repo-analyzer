"""Generate a static HTML site for GitHub Pages. Pre-computes analysis for demo users."""
import os, sys, json, base64, io
import pandas as pd
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

BASE = r"C:\Users\shi_h\Desktop\24211870223_时航_GitHub仓库数据分析系统"
SRC = os.path.join(BASE, "src")
sys.path.insert(0, SRC)

from github_api import GitHubAPI, resolve_token
from analyze import GitHubAnalyzer
from visualize import GitHubVisualizer

DOCS_DIR = os.path.join(BASE, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

DEMO_USERS = [
    {"name": "torvalds", "label": "Linus Torvalds", "desc": "Linux 内核之父"},
    {"name": "microsoft", "label": "Microsoft", "desc": "微软开源帝国"},
    {"name": "google", "label": "Google", "desc": "谷歌开源力量"},
]

DATA_DIR = os.path.join(BASE, "data")


def img_to_b64(fig, fmt="png"):
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=120, bbox_inches="tight", facecolor="white", edgecolor="none")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def get_chart_html(fig, css_class=""):
    b64 = img_to_b64(fig)
    return f'<img src="data:image/png;base64,{b64}" class="{css_class}" style="max-width:100%;height:auto;display:block;margin:10px auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">'

def analyze_user(name: str) -> dict:
    """Analyze a single user and return all results."""
    csv_path = os.path.join(DATA_DIR, f"repos_{name}.csv")

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        print(f"  Loaded cached data for {name}: {len(df)} repos")
    else:
        token = resolve_token()
        api = GitHubAPI(token=token)
        repos = api.collect_repo_data(name, max_repos=200)
        if not repos:
            return None
        df = pd.DataFrame(repos)
        df.to_csv(csv_path, index=False)
        print(f"  Fetched {len(df)} repos for {name}")

    analyzer = GitHubAnalyzer(df)
    viz = GitHubVisualizer(df)

    # Call all chart methods (they save to disk)
    viz.chart_top_stars()
    viz.chart_language_pie()
    viz.chart_stars_vs_forks()
    viz.chart_creation_timeline()
    viz.chart_stars_histogram()
    viz.chart_language_stars()
    viz.chart_topics_wordcloud()
    viz.chart_activity_scores(analyzer)
    viz.chart_language_radar(analyzer)

    health = analyzer.project_health()
    if health:
        viz.chart_project_health(health)

    # Read generated images and base64 encode
    chart_files = {
        "Stars TOP 排行": "01_top_stars.png",
        "语言分布": "02_language_pie.png",
        "Stars vs Forks": "03_stars_vs_forks.png",
        "创建趋势": "04_creation_timeline.png",
        "Stars 分布": "05_stars_histogram.png",
        "语言均星": "06_language_stars.png",
        "Topics 词云": "07_topics_wordcloud.png",
        "活跃度评分": "08_activity_scores.png",
        "语言趋势雷达": "09_language_radar.png",
        "项目健康度": "10_project_health.png",
    }

    charts_html = {}
    output_dir = viz.output_dir
    for label, fname in chart_files.items():
        path = os.path.join(output_dir, fname)
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            charts_html[label] = f'<img src="data:image/png;base64,{b64}" style="max-width:100%;height:auto;display:block;margin:10px auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">'

    stats = analyzer.basic_stats()
    report = analyzer.summary_report()
    activity = analyzer.activity_summary()

    return {
        "name": name,
        "stats": stats,
        "report": report,
        "activity": activity,
        "health": health,
        "charts_html": charts_html,
    }

