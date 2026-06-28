"""
GitHub 数据分析 · 交互式 Web 应用
基于 Streamlit 构建的优美交互界面。

启动方式:
    streamlit run app.py
    streamlit run app.py --server.port 8502
"""

import os
import sys
import traceback
from io import BytesIO

import pandas as pd
import streamlit as st

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from github_api import GitHubAPI, resolve_token
from trending import TrendingScraper
from analyze import GitHubAnalyzer
from visualize import GitHubVisualizer
from pdf_export import export_pdf_to_bytes

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Page Config ─────────────────────────────────────────────
st.set_page_config(
    page_title="GitHub 数据分析系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    .repo-card {
        background: linear-gradient(135deg, #ffffff 0%, #f6f8fa 100%);
        border: 1px solid #d0d7de; border-radius: 12px; padding: 1.2rem 1.4rem;
        margin-bottom: 0.8rem; transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .repo-card:hover { border-color: #2dba4e; box-shadow: 0 4px 12px rgba(45,186,78,0.12); transform: translateY(-1px); }
    .repo-card h3 { margin: 0 0 0.3rem 0; font-size: 1.05rem; }
    .repo-card h3 a { color: #0969da; text-decoration: none; font-weight: 600; }
    .repo-card h3 a:hover { text-decoration: underline; }
    .repo-card .desc { color: #57606a; font-size: 0.85rem; margin: 0.3rem 0 0.6rem 0; line-height: 1.4; }
    .repo-card .meta { display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.8rem; color: #57606a; }
    .repo-card .meta span { display: inline-flex; align-items: center; gap: 4px; }
    .lang-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

    .compare-card {
        background: #f6f8fa; border: 2px solid #d0d7de; border-radius: 12px;
        padding: 1rem 1.2rem; text-align: center;
    }
    .compare-card.winner { border-color: #2dba4e; background: #f0faf3; }
    .compare-card .big { font-size: 1.6rem; font-weight: 700; color: #1f2328; }
    .compare-card .label { font-size: 0.8rem; color: #57606a; margin-top: 2px; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f6f8fa 0%, #ffffff 100%);
        border-right: 1px solid #d0d7de;
    }

    .app-header { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0 1rem 0; border-bottom: 2px solid #d0d7de; margin-bottom: 1.5rem; }
    .app-header .icon { font-size: 2rem; }
    .app-header .title { font-size: 1.5rem; font-weight: 700; color: #1f2328; }
    .app-header .subtitle { font-size: 0.85rem; color: #57606a; }

    .footer { text-align: center; color: #8b949e; font-size: 0.75rem; padding: 2rem 0 0.5rem 0; border-top: 1px solid #d0d7de; margin-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ── Language Colors ──────────────────────────────────────────
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584", "C": "#555555",
    "C++": "#f34b7d", "C#": "#178600", "Ruby": "#701516", "Swift": "#F05138",
    "Kotlin": "#A97BFF", "PHP": "#4F5D95", "Scala": "#c22d40", "Shell": "#89e051",
    "HTML": "#e34c26", "CSS": "#563d7c", "Vue": "#41b883", "Jupyter": "#DA5B0B",
    "Dart": "#00B4AB", "R": "#198CE7", "Lua": "#000080", "MATLAB": "#e16737",
    "Other": "#8b8b8b",
}


def color_for_lang(lang: str) -> str:
    return LANG_COLORS.get(lang, "#8b8b8b")


# ── Cached Data Fetching ─────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_repos(user: str, token: str, max_repos: int) -> pd.DataFrame:
    """Cached: fetch repo data from GitHub API or local CSV."""
    csv_path = os.path.join(DATA_DIR, f"repos_{user}.csv")
    api = GitHubAPI(token=token)
    repos = api.collect_repo_data(user, max_repos=max_repos)
    if not repos:
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path, encoding="utf-8-sig")
        return pd.DataFrame()
    df = pd.DataFrame(repos)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_trending(period: str, lang: str, token: str, max_items: int = 25) -> list[dict]:
    """Cached: fetch trending repos from GitHub Search API."""
    scraper = TrendingScraper(token=token)
    if lang == "全部":
        return getattr(scraper, period)(max_items=max_items)
    return scraper.by_language(lang, period=period, max_items=max_items)


def _build_charts(df: pd.DataFrame, user_label: str) -> dict[str, BytesIO]:
    """Generate charts from a dataframe, returning {label: buffer}."""
    viz = GitHubVisualizer(df, OUTPUT_DIR)
    analyzer = GitHubAnalyzer(df)
    chart_bufs: dict[str, BytesIO] = {}
    methods = [
        (viz.chart_top_stars, "Top Stars"),
        (viz.chart_language_pie, "Language Pie"),
        (viz.chart_stars_vs_forks, "Stars Vs Forks"),
        (viz.chart_creation_timeline, "Creation Timeline"),
        (viz.chart_stars_histogram, "Stars Histogram"),
        (viz.chart_language_stars, "Language Stars"),
        (viz.chart_topics_wordcloud, "Topics Wordcloud"),
        (lambda: viz.chart_activity_scores(analyzer), "Activity Scores"),
        (lambda: viz.chart_language_radar(analyzer), "Language Radar"),
        (lambda: viz.chart_cluster_scatter(analyzer), "Cluster Scatter"),
        (lambda: viz.chart_regression_comparison(analyzer), "Regression Comparison"),
    ]
    for method, label in methods:
        try:
            path = method()
            with open(path, "rb") as f:
                buf = BytesIO(f.read())
            buf.seek(0)
            chart_bufs[label] = buf
        except Exception:
            pass
    return chart_bufs


def run_single_analysis(user: str, token: str, max_repos: int):
    """Full pipeline for one user (with caching). Returns (df, stats, report, charts, chart_paths)."""
    with st.status(f"正在连接 GitHub API 获取 **{user}** 的仓库数据...", expanded=True) as status:
        df = _fetch_repos(user, token, max_repos)
        if df.empty:
            status.update(label="未获取到数据", state="error")
            return None, {}, "", {}, []
        status.update(label=f"数据采集完成 — {len(df)} 个仓库", state="complete")

    analyzer = GitHubAnalyzer(df)
    stats = analyzer.basic_stats()
    act_summary = analyzer.activity_summary()
    stats.update(act_summary)
    report = analyzer.summary_report()
    charts = _build_charts(df, user)

    # 数据建模结果
    cluster_result = None
    regression_result = None
    try:
        cluster_result = analyzer.cluster_repos()
    except Exception:
        pass
    try:
        regression_result = analyzer.regression_predict()
    except Exception:
        pass

    # Collect chart file paths for PDF export (only this analysis's charts)
    chart_names = [
        "01_top_stars.png", "02_language_pie.png", "03_stars_vs_forks.png",
        "04_creation_timeline.png", "05_stars_histogram.png",
        "06_language_stars.png", "07_topics_wordcloud.png",
        "08_activity_scores.png", "09_language_radar.png",
        "10_cluster_scatter.png", "11_regression_comparison.png",
    ]
    chart_paths = [os.path.join(OUTPUT_DIR, n) for n in chart_names
                   if os.path.exists(os.path.join(OUTPUT_DIR, n))]
    return df, stats, report, charts, chart_paths, cluster_result, regression_result


# ── Sidebar ──────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 GitHub 分析")
    st.markdown("---")

    st.markdown("### 🔐 GitHub Token")
    token = st.text_input(
        "Personal Access Token",
        type="password",
        placeholder="ghp_xxx（可选，提升限流）",
        help="未认证 60次/小时，认证后 5000次/小时。也可通过环境变量 GITHUB_TOKEN 设置。",
    )
    # Show env token status
    env_token = resolve_token("")
    if env_token and not token:
        st.caption("✅ 已从环境变量 GITHUB_TOKEN 读取 Token")

    st.markdown("---")
    st.markdown("### 📋 导航")
    page = st.radio(
        "选择功能",
        ["🏠 热门项目", "🔍 用户仓库分析", "⚔️ 对比分析"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### ⚙️ 设置")
    max_repos = st.slider("最大仓库数", 10, 300, 200, step=10)

    # Cache info
    st.markdown("---")
    if st.button("🧹 清除缓存", use_container_width=True):
        st.cache_data.clear()
        st.toast("缓存已清除")

    st.markdown(
        "<div style='font-size:0.75rem;color:#8b949e;margin-top:1rem;'>"
        "Powered by Streamlit + GitHub API<br>"
        "数据采集 · 分析 · 可视化"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Shared Quick Select ──────────────────────────────────────

QUICK_USERS = {
    "torvalds": "Linus Torvalds",
    "microsoft": "Microsoft",
    "google": "Google",
    "TheAlgorithms": "The Algorithms",
    "facebook": "Meta",
    "apple": "Apple",
}

# ── Page: Trending ───────────────────────────────────────────

if page == "🏠 热门项目":
    st.markdown(
        '<div class="app-header">'
        '<span class="icon">🔥</span>'
        '<span class="title">GitHub 热门新项目</span>'
        '<span class="subtitle">— 发现正在流行的开源仓库</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_daily, tab_weekly, tab_monthly = st.tabs(["📅 今日热门", "📆 本周热门", "🗓️ 本月热门"])

    for tab, period_key, period_label in [
        (tab_daily, "daily", "今日"),
        (tab_weekly, "weekly", "本周"),
        (tab_monthly, "monthly", "本月"),
    ]:
        with tab:
            lang_filter = st.selectbox(
                "筛选语言",
                ["全部", "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust",
                 "C", "C++", "Ruby", "Swift", "Kotlin", "R", "Other"],
                key=f"lang_{period_key}",
            )

            load_btn = st.button(f"🔄 获取{period_label}热门项目", key=f"btn_{period_key}")

            data = []
            if load_btn:
                with st.spinner(f"正在搜索{period_label}热门仓库..."):
                    try:
                        data = _fetch_trending(
                            period_key, lang_filter, resolve_token(token),
                        )
                        st.session_state[f"trending_{period_key}"] = data
                    except RuntimeError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"请求失败: {e}")
            else:
                data = st.session_state.get(f"trending_{period_key}", [])

            if data:
                st.caption(f"共 {len(data)} 个仓库")

                cols = st.columns(4)
                with cols[0]: st.metric("📦 展示仓库", len(data))
                with cols[1]: st.metric("⭐ 总星数", f"{sum(r['stars'] for r in data):,}")
                with cols[2]:
                    langs = {r["language"] for r in data}
                    st.metric("🔤 语言数", len(langs))
                with cols[3]:
                    top_lang = pd.Series([r["language"] for r in data]).mode()
                    st.metric("🏷️ 主流语言", top_lang.iloc[0] if len(top_lang) else "N/A")

                st.markdown("---")

                for i, repo in enumerate(data):
                    if i % 2 == 0:
                        col1, col2 = st.columns(2)
                    col = col1 if i % 2 == 0 else col2
                    with col:
                        lang = repo["language"]
                        desc = repo["description"] if repo["description"] else "暂无描述"
                        st.markdown(f"""
                        <div class="repo-card">
                            <h3><a href="{repo['html_url']}" target="_blank">📁 {repo['full_name']}</a></h3>
                            <div class="desc">{desc[:120]}{'...' if len(desc) > 120 else ''}</div>
                            <div class="meta">
                                <span>⭐ {repo['stars']:,}</span>
                                <span>⑂ {repo['forks']:,}</span>
                                <span><span class="lang-dot" style="background:{color_for_lang(lang)};"></span> {lang}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                df_trend = pd.DataFrame(data)
                st.download_button(
                    f"📥 下载 {period_label}热门数据 (CSV)",
                    df_trend.to_csv(index=False).encode("utf-8-sig"),
                    f"trending_{period_key}.csv", "text/csv",
                )

# ── Page: Single User Analysis ───────────────────────────────

elif page == "🔍 用户仓库分析":
    st.markdown(
        '<div class="app-header">'
        '<span class="icon">🔍</span>'
        '<span class="title">用户仓库分析</span>'
        '<span class="subtitle">— 深度分析任意 GitHub 用户/组织的公开仓库</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 快捷选择: 点击按钮后写入 session_state["_search_user"] 并 rerun
    # text_input 有 key 时会从 session_state 恢复值，所以下次 rerun 就能显示
    user = st.text_input(
        "GitHub 用户名或组织名",
        placeholder="例如: torvalds, microsoft, google, TheAlgorithms",
        label_visibility="collapsed",
        key="_search_user",
    )

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption("快捷选择:")
    with col_b:
        analyze_btn = st.button("🚀 开始分析", use_container_width=True, type="primary")

    quick_cols = st.columns(len(QUICK_USERS))
    for j, (quser, qlabel) in enumerate(QUICK_USERS.items()):
        with quick_cols[j]:
            if st.button(qlabel, key=f"q_{quser}", use_container_width=True):
                st.session_state["_search_user"] = quser
                st.rerun()

    if analyze_btn and user.strip():
        user = user.strip()
        st.session_state["quick_user"] = ""

        try:
            df, stats, report, charts, chart_paths, cluster_result, regression_result = run_single_analysis(user, resolve_token(token), max_repos)
            st.session_state["df"] = df
            st.session_state["stats"] = stats
            st.session_state["report"] = report
            st.session_state["charts"] = charts
            st.session_state["chart_paths"] = chart_paths
            st.session_state["analysis_user"] = user
            st.session_state["cluster_result"] = cluster_result
            st.session_state["regression_result"] = regression_result
        except Exception:
            st.error(f"分析失败:\n```\n{traceback.format_exc()}\n```")

    df = st.session_state.get("df")
    stats = st.session_state.get("stats")
    report = st.session_state.get("report")
    charts = st.session_state.get("charts")

    if stats and df is not None and len(df) > 0:
        st.markdown("---")
        st.markdown("### 📈 关键指标")
        mc = st.columns(6)
        metrics = [
            ("仓库总数", stats["仓库总数"]),
            ("⭐ 总星数", f"{stats['总星数(Stars)']:,}"),
            ("平均星数", f"{stats['平均星数']:,}"),
            ("最高星数", f"{stats['最高星数']:,}"),
            ("主要语言", stats["主要语言"]),
            ("🟢 平均活跃度", stats.get("平均活跃度", "N/A")),
        ]
        for j, (label, value) in enumerate(metrics):
            with mc[j]: st.metric(label, value)

        # 活跃度分布
        act_high = stats.get("高活跃(≥70)", 0)
        act_mid = stats.get("中活跃(40-69)", 0)
        act_low = stats.get("低活跃(<40)", 0)
        ac1, ac2, ac3 = st.columns(3)
        with ac1: st.metric("🟢 高活跃 (≥70)", act_high)
        with ac2: st.metric("🟡 中活跃 (40-69)", act_mid)
        with ac3: st.metric("🔴 低活跃 (<40)", act_low)

        st.markdown("---")
        st.markdown("### 📊 可视化图表")

        if charts:
            # 用中文标签
            label_map = {
                "Top Stars": "⭐ Stars TOP 排行",
                "Language Pie": "🔤 语言分布饼图",
                "Stars Vs Forks": "📈 Stars vs Forks",
                "Creation Timeline": "📅 创建时间趋势",
                "Stars Histogram": "📊 Stars 分布直方图",
                "Language Stars": "🏆 语言均星排行",
                "Topics Wordcloud": "☁️ Topics 词云",
                "Activity Scores": "🟢 仓库活跃度评分",
                "Language Radar": "🕸️ 语言趋势雷达图",
                "Cluster Scatter": "🔬 仓库聚类分析",
                "Regression Comparison": "📉 Stars 预测回归模型",
            }
            chart_keys = list(charts.keys())
            display_labels = [label_map.get(k, k) for k in chart_keys]
            tabs = st.tabs(display_labels)
            for t, key in zip(tabs, chart_keys):
                with t:
                    st.image(charts[key], use_column_width=True)

        # 活跃度明细表
        st.markdown("---")
        st.markdown("### 🟢 仓库活跃度明细")
        try:
            analyzer = GitHubAnalyzer(df)
            act_df = analyzer.activity_scores()
            display_cols = ["name", "language", "stars", "activity_score"]
            display_names = {
                "name": "仓库名", "language": "语言",
                "stars": "Stars", "activity_score": "活跃度评分",
            }
            st.dataframe(
                act_df[display_cols].rename(columns=display_names),
                use_container_width=True, hide_index=True,
                height=min(len(act_df) * 35 + 40, 400),
            )
        except Exception as e:
            st.warning(f"活跃度数据加载失败: {e}")

        # ── 聚类分析结果展示 ──────────────────────────────────
        cluster_result = st.session_state.get("cluster_result")
        if cluster_result:
            st.markdown("---")
            st.markdown("### 🔬 聚类分析结果（K-Means）")
            st.caption(f"特征维度: {', '.join(cluster_result['features'])} | 轮廓系数: {cluster_result.get('silhouette_score', 'N/A')}")

            # 聚类卡片
            cluster_cards = st.columns(len(cluster_result["cluster_names"]))
            for i, (label, info) in enumerate(cluster_result["cluster_names"].items()):
                with cluster_cards[i]:
                    color = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12"][label % 4]
                    st.markdown(f"""
                    <div style="background:{color}15;border:2px solid {color};border-radius:12px;padding:1rem;text-align:center;">
                        <div style="font-size:0.8rem;color:{color};font-weight:600;">聚类 {label}</div>
                        <div style="font-size:1.1rem;font-weight:700;margin:0.3rem 0;">{info['name']}</div>
                        <div style="font-size:0.8rem;color:#666;">{info['count']} 个仓库 | 平均 {info['avg_stars']:.0f} ⭐</div>
                    </div>
                    """, unsafe_allow_html=True)

            # 聚类中心表
            with st.expander("查看聚类中心详情"):
                st.dataframe(cluster_result["centers"], use_container_width=True)

        # ── 回归模型结果展示 ──────────────────────────────────
        regression_result = st.session_state.get("regression_result")
        if regression_result:
            st.markdown("---")
            st.markdown("### 📉 Stars 预测回归模型")
            st.caption(f"特征: {', '.join(regression_result['features'])} | 训练集: {regression_result['train_size']} | 测试集: {regression_result['test_size']}")

            reg_cols = st.columns(len(regression_result["metrics"]))
            for i, (model_name, data) in enumerate(regression_result["metrics"].items()):
                with reg_cols[i]:
                    r2_color = "#2ecc71" if data["R2"] > 0.5 else ("#f39c12" if data["R2"] > 0 else "#e74c3c")
                    st.markdown(f"""
                    <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:12px;padding:1.2rem;">
                        <div style="font-size:0.9rem;font-weight:600;color:#333;margin-bottom:0.8rem;">{model_name}</div>
                        <div style="margin:0.3rem 0;"><span style="color:#666;">R²:</span> <span style="color:{r2_color};font-weight:700;">{data['R2']:.4f}</span></div>
                        <div style="margin:0.3rem 0;"><span style="color:#666;">MAE:</span> <span style="font-weight:600;">{data['MAE']:.0f}</span></div>
                        <div style="margin:0.3rem 0;"><span style="color:#666;">RMSE:</span> <span style="font-weight:600;">{data['RMSE']:.0f}</span></div>
                    </div>
                    """, unsafe_allow_html=True)

            # 特征重要性
            with st.expander("查看特征重要性 / 回归系数"):
                rf_data = regression_result["metrics"].get("随机森林", {})
                if "feature_importance" in rf_data:
                    importance_df = pd.DataFrame([
                        {"特征": k, "重要性": v}
                        for k, v in rf_data["feature_importance"].items()
                    ]).sort_values("重要性", ascending=False)
                    st.dataframe(importance_df, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📝 分析报告")
        with st.expander("查看完整报告", expanded=False):
            st.code(report, language="text")

        with st.expander("🔎 查看原始数据", expanded=False):
            cols = [c for c in ["name", "language", "stars", "forks", "open_issues", "created_at"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)

        if df is not None:
            col_csv, col_pdf = st.columns(2)
            with col_csv:
                st.download_button(
                    "📥 下载分析数据 (CSV)",
                    df.to_csv(index=False).encode("utf-8-sig"),
                    f"repos_{st.session_state.get('analysis_user', 'user')}.csv",
                    "text/csv",
                    use_container_width=True,
                )
            with col_pdf:
                chart_paths = st.session_state.get("chart_paths", [])
                if chart_paths and stats:
                    pdf_buf = export_pdf_to_bytes(
                        st.session_state.get("analysis_user", "user"),
                        stats, report, chart_paths,
                    )
                    st.download_button(
                        "📄 下载 PDF 报告",
                        pdf_buf,
                        f"report_{st.session_state.get('analysis_user', 'user')}.pdf",
                        "application/pdf",
                        use_container_width=True,
                    )

# ── Page: Comparison ─────────────────────────────────────────

elif page == "⚔️ 对比分析":
    st.markdown(
        '<div class="app-header">'
        '<span class="icon">⚔️</span>'
        '<span class="title">对比分析</span>'
        '<span class="subtitle">— 并排比较两个 GitHub 用户/组织的开源数据</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        user_a = st.text_input(
            "用户 A", placeholder="例如: torvalds", key="cmp_a",
            label_visibility="collapsed",
        )
    with col2:
        user_b = st.text_input(
            "用户 B", placeholder="例如: microsoft", key="cmp_b",
            label_visibility="collapsed",
        )

    st.caption("快捷选择:")
    qc = st.columns(len(QUICK_USERS))
    for j, (quser, qlabel) in enumerate(QUICK_USERS.items()):
        with qc[j]:
            if st.button(qlabel, key=f"cmp_q_{quser}", use_container_width=True):
                if not st.session_state.get("cmp_a_input"):
                    st.session_state["cmp_a_input"] = quser
                elif not st.session_state.get("cmp_b_input"):
                    st.session_state["cmp_b_input"] = quser
                st.rerun()

    if st.session_state.get("cmp_a_input"):
        st.session_state["cmp_a"] = st.session_state.pop("cmp_a_input")
    if st.session_state.get("cmp_b_input"):
        st.session_state["cmp_b"] = st.session_state.pop("cmp_b_input")

    compare_btn = st.button("⚔️ 开始对比", use_container_width=True, type="primary")

    if compare_btn and user_a.strip() and user_b.strip():
        user_a = user_a.strip()
        user_b = user_b.strip()
        if user_a == user_b:
            st.error("两个用户不能相同！")
        else:
            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown(f"### 📊 {user_a}")
                with st.spinner(f"正在分析 {user_a}..."):
                    try:
                        df_a, stats_a, report_a, charts_a, _ = run_single_analysis(
                            user_a, resolve_token(token), max_repos,
                        )
                        st.session_state["cmp_df_a"] = df_a
                        st.session_state["cmp_stats_a"] = stats_a
                        st.session_state["cmp_charts_a"] = charts_a
                    except Exception:
                        st.error(traceback.format_exc())
                        stats_a = {}

            with col_right:
                st.markdown(f"### 📊 {user_b}")
                with st.spinner(f"正在分析 {user_b}..."):
                    try:
                        df_b, stats_b, report_b, charts_b, _ = run_single_analysis(
                            user_b, resolve_token(token), max_repos,
                        )
                        st.session_state["cmp_df_b"] = df_b
                        st.session_state["cmp_stats_b"] = stats_b
                        st.session_state["cmp_charts_b"] = charts_b
                    except Exception:
                        st.error(traceback.format_exc())
                        stats_b = {}

    # Show comparison results
    stats_a = st.session_state.get("cmp_stats_a")
    stats_b = st.session_state.get("cmp_stats_b")

    if stats_a and stats_b:
        st.markdown("---")
        st.markdown("### 📈 关键指标对比")

        # Determine winners
        def cmp_metric(key, bigger_is_better=True):
            a_val = stats_a.get(key, 0)
            b_val = stats_b.get(key, 0)
            if isinstance(a_val, str):
                a_val = 0
            if isinstance(b_val, str):
                b_val = 0
            if bigger_is_better:
                return "a" if a_val > b_val else ("b" if b_val > a_val else "tie")
            else:
                return "a" if a_val < b_val else ("b" if b_val < a_val else "tie")

        # Numeric comparison
        pairs = [
            ("仓库总数", "仓库总数", False, "📦"),
            ("总星数(Stars)", "总星数", True, "⭐"),
            ("平均星数", "平均星数", True, "📊"),
            ("最高星数", "最高星数", True, "🏆"),
            ("语言种类数", "语言种类数", False, "🔤"),
            ("平均活跃度", "平均活跃度", True, "🟢"),
        ]

        for stat_key, label, bigger, icon in pairs:
            c1, c2, c3 = st.columns([1, 1, 1])
            a_val = stats_a.get(stat_key, 0) if stat_key in stats_a else stats_a.get(label, 0)
            b_val = stats_b.get(stat_key, 0) if stat_key in stats_b else stats_b.get(label, 0)
            winner = cmp_metric(stat_key, bigger) if stat_key in stats_a else cmp_metric(label, bigger)

            a_cls = "compare-card winner" if winner == "a" else "compare-card"
            b_cls = "compare-card winner" if winner == "b" else "compare-card"

            with c1:
                st.markdown(f"<div class='{a_cls}'><div class='big'>{icon} {a_val}</div><div class='label'>{user_a}</div></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='text-align:center;padding-top:1rem;font-size:1.2rem;'>{label}</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='{b_cls}'><div class='big'>{icon} {b_val}</div><div class='label'>{user_b}</div></div>", unsafe_allow_html=True)

        # Language breakdown side by side
        st.markdown("---")
        st.markdown("### 🔤 语言分布对比")
        cl, cr = st.columns(2)
        charts_a = st.session_state.get("cmp_charts_a", {})
        charts_b = st.session_state.get("cmp_charts_b", {})
        with cl:
            st.caption(user_a)
            if charts_a:
                for key, buf in charts_a.items():
                    if "language pie" in key.lower() or "language stars" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
        with cr:
            st.caption(user_b)
            if charts_b:
                for key, buf in charts_b.items():
                    if "language pie" in key.lower() or "language stars" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)

        # Side-by-side charts: stars histogram
        st.markdown("### 📊 Stars 分布对比")
        cl2, cr2 = st.columns(2)
        with cl2:
            st.caption(user_a)
            if charts_a:
                for key, buf in charts_a.items():
                    if "stars histogram" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break
        with cr2:
            st.caption(user_b)
            if charts_b:
                for key, buf in charts_b.items():
                    if "stars histogram" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break

        # Wordclouds
        st.markdown("### ☁️ Topics 词云对比")
        cl3, cr3 = st.columns(2)
        with cl3:
            st.caption(user_a)
            if charts_a:
                for key, buf in charts_a.items():
                    if "wordcloud" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break
        with cr3:
            st.caption(user_b)
            if charts_b:
                for key, buf in charts_b.items():
                    if "wordcloud" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break

        # Activity scores comparison
        st.markdown("### 🟢 活跃度评分对比")
        cl4, cr4 = st.columns(2)
        with cl4:
            st.caption(user_a)
            if charts_a:
                for key, buf in charts_a.items():
                    if "activity" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break
        with cr4:
            st.caption(user_b)
            if charts_b:
                for key, buf in charts_b.items():
                    if "activity" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break

        # Language radar comparison
        st.markdown("### 🕸️ 语言趋势雷达图对比")
        cl5, cr5 = st.columns(2)
        with cl5:
            st.caption(user_a)
            if charts_a:
                for key, buf in charts_a.items():
                    if "radar" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break
        with cr5:
            st.caption(user_b)
            if charts_b:
                for key, buf in charts_b.items():
                    if "radar" in key.lower():
                        buf.seek(0)
                        st.image(buf, use_column_width=True)
                        break

# ── Footer ───────────────────────────────────────────────────

st.markdown(
    '<div class="footer">GitHub 数据分析系统 © 2026 · '
    'Built with Streamlit · Data via GitHub REST API v3</div>',
    unsafe_allow_html=True,
)
