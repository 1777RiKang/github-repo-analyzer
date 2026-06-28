"""
数据可视化模块
基于 GitHub 仓库数据，使用 Matplotlib 生成分析图表。

图表列表：
  1. Stars TOP10 横向柱状图
  2. 编程语言分布饼图
  3. Stars vs Forks 散点图 + 回归线
  4. 仓库创建时间趋势图
  5. Stars 分布直方图
  6. 语言平均星数排行榜
  7. Topics 词云
"""

import os
from io import BytesIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei",
    "Noto Sans CJK SC", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


class GitHubVisualizer:
    """GitHub 仓库数据可视化器。"""

    def __init__(
        self, df: pd.DataFrame, output_dir: str = "./output"
    ) -> None:
        self.df = df.copy()
        self.df = self.df[self.df["is_fork"] == False]
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 时间预处理
        if "created_at_dt" not in self.df.columns:
            self.df["created_at_dt"] = pd.to_datetime(
                self.df["created_at"], errors="coerce"
            )

    def _save_fig(self, fig: plt.Figure, filename: str) -> str:
        """Save figure to disk and return path."""
        path = os.path.join(self.output_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    @staticmethod
    def _fig_to_bytes(fig: plt.Figure) -> BytesIO:
        """Render figure to a BytesIO buffer (no disk IO)."""
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf

    # ── 图表生成 ──────────────────────────────────────────

    def chart_top_stars(self) -> str:
        """Stars TOP10 横向柱状图。"""
        n = min(len(self.df), 10)
        topn = self.df.nlargest(n, "stars")
        topn["label"] = topn["name"].apply(
            lambda s: s[:22] + "..." if len(s) > 22 else s
        )

        fig, ax = plt.subplots(figsize=(12, 6))
        colors = plt.cm.YlOrRd(0.3 + np.linspace(0, 0.7, n))
        bars = ax.barh(
            range(n), topn["stars"].values,
            color=colors[::-1], edgecolor="#333",
        )
        ax.set_yticks(range(n))
        ax.set_yticklabels(topn["label"].values[::-1], fontsize=10)
        ax.set_xlabel("Stars", fontsize=12)
        ax.set_title(f"GitHub Stars Top {n} 仓库", fontsize=14, fontweight="bold")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, _: f"{x/1000:.0f}k" if x >= 1000 else str(int(x))
        ))
        ax.grid(axis="x", alpha=0.3)

        for bar, val, lang in zip(
            bars, topn["stars"].values[::-1], topn["language"].values[::-1]
        ):
            label = f"{val/1000:.1f}k " if val >= 1000 else str(val)
            ax.text(
                bar.get_width() + max(topn["stars"]) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{label} ({lang})",
                va="center", fontsize=8,
            )

        plt.tight_layout()
        return self._save_fig(fig, "01_top_stars.png")

    def chart_language_pie(self) -> str:
        """编程语言分布饼图。"""
        lang_counts = self.df["language"].value_counts()
        # 合并 <2% 的为 "Other"
        threshold = len(self.df) * 0.02
        main = lang_counts[lang_counts >= threshold]
        other_sum = lang_counts[lang_counts < threshold].sum()
        if other_sum > 0:
            main["Other"] = other_sum

        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.Set3(range(len(main)))
        wedges, texts, autotexts = ax.pie(
            main.values, labels=main.index, autopct="%1.1f%%",
            colors=colors, startangle=90,
            pctdistance=0.85,
        )
        for t in autotexts:
            t.set_fontsize(8)
        for t in texts:
            t.set_fontsize(10)

        ax.set_title("编程语言分布", fontsize=14, fontweight="bold")
        plt.tight_layout()
        return self._save_fig(fig, "02_language_pie.png")

    def chart_stars_vs_forks(self) -> str:
        """Stars vs Forks 散点图 + 回归线。"""
        fig, ax = plt.subplots(figsize=(10, 6))

        x = self.df["stars"].values.astype(float)
        y = self.df["forks"].values.astype(float)

        # Log scale 更清晰
        ax.scatter(x, y, alpha=0.5, s=40, c="#2dba4e", edgecolors="white")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Stars (log)", fontsize=12)
        ax.set_ylabel("Forks (log)", fontsize=12)
        ax.set_title("Stars vs Forks 关系图", fontsize=14, fontweight="bold")
        ax.grid(alpha=0.3)

        # 标注极端值
        for idx in self.df.nlargest(3, "stars").index:
            row = self.df.loc[idx]
            ax.annotate(
                row["name"][:15],
                (row["stars"], row["forks"]),
                fontsize=7,
                arrowprops=dict(arrowstyle="->", color="gray"),
            )

        plt.tight_layout()
        return self._save_fig(fig, "03_stars_vs_forks.png")

    def chart_creation_timeline(self) -> str:
        """仓库创建时间趋势（按年份）。"""
        df = self.df.copy()
        df["year"] = df["created_at_dt"].dt.year
        yearly = df.groupby("year").agg(
            新建仓库=("name", "count"),
            累计星数=("stars", "sum"),
        ).reset_index()
        yearly = yearly.dropna(subset=["year"])
        yearly["year"] = yearly["year"].astype(int)

        fig, ax1 = plt.subplots(figsize=(14, 6))

        bars = ax1.bar(
            yearly["year"].values, yearly["新建仓库"].values,
            color="#2dba4e", alpha=0.7, label="新建仓库数",
        )
        ax1.set_xlabel("年份", fontsize=12)
        ax1.set_ylabel("新建仓库数", color="#2dba4e", fontsize=12)
        ax1.tick_params(axis="y", labelcolor="#2dba4e")

        ax2 = ax1.twinx()
        ax2.plot(
            yearly["year"].values, yearly["累计星数"].values / 1000,
            color="#e74c3c", linewidth=2, marker="o", label="累计星数(k)",
        )
        ax2.set_ylabel("累计星数 (k)", color="#e74c3c", fontsize=12)
        ax2.tick_params(axis="y", labelcolor="#e74c3c")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
        ax1.set_title("仓库创建趋势", fontsize=14, fontweight="bold")
        ax1.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        return self._save_fig(fig, "04_creation_timeline.png")

    def chart_stars_histogram(self) -> str:
        """Stars 分布直方图。"""
        fig, ax = plt.subplots(figsize=(10, 6))

        stars = self.df["stars"].values
        bins = [0, 5, 10, 50, 100, 500, 1000, 5000, max(stars) + 1]
        labels = ["0-5", "5-10", "10-50", "50-100", "100-500", "500-1K", "1K-5K", "5K+"]

        counts, _ = np.histogram(stars, bins=bins)
        colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(counts)))
        bars = ax.bar(range(len(counts)), counts, color=colors, edgecolor="#333")

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_xlabel("Stars 区间", fontsize=12)
        ax.set_ylabel("仓库数量", fontsize=12)
        ax.set_title("Stars 分布直方图", fontsize=14, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(counts) * 0.02,
                    str(count), ha="center", fontsize=9,
                )

        plt.tight_layout()
        return self._save_fig(fig, "05_stars_histogram.png")

    def chart_language_stars(self) -> str:
        """语言平均星数排行榜。"""
        grouped = self.df.groupby("language").agg(
            仓库数=("name", "count"),
            平均星数=("stars", "mean"),
        )
        grouped = grouped[grouped["仓库数"] >= 2]
        top_lang = grouped.nlargest(12, "平均星数")

        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.YlOrRd(0.3 + np.linspace(0, 0.7, len(top_lang)))

        bars = ax.barh(
            range(len(top_lang)),
            top_lang["平均星数"].values,
            color=colors[::-1], edgecolor="#333",
        )
        ax.set_yticks(range(len(top_lang)))
        ax.set_yticklabels(top_lang.index.values, fontsize=10)
        ax.set_xlabel("平均 Stars", fontsize=12)
        ax.set_title("各语言平均 Stars 排行", fontsize=14, fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

        for bar, val, cnt in zip(
            bars, top_lang["平均星数"].values, top_lang["仓库数"].values
        ):
            ax.text(
                bar.get_width() + max(top_lang["平均星数"]) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.0f} ({cnt} repos)",
                va="center", fontsize=8,
            )

        plt.tight_layout()
        return self._save_fig(fig, "06_language_stars.png")

    def chart_topics_wordcloud(self) -> str:
        """Topics 主题标签词云图（按星数加权）。"""
        from wordcloud import WordCloud

        # 构建 topic → 累计星数 的加权词频
        topic_weights: dict[str, int] = {}
        for _, row in self.df[["topics", "stars"]].dropna().iterrows():
            if row["topics"]:
                for topic in row["topics"].split(","):
                    topic = topic.strip()
                    if topic:
                        topic_weights[topic] = topic_weights.get(topic, 0) + int(row["stars"])

        if not topic_weights:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.text(0.5, 0.5, "暂无 Topics 数据", ha="center", va="center",
                    fontsize=16, color="#8b8b8b")
            ax.axis("off")
            plt.tight_layout()
            return self._save_fig(fig, "07_topics_wordcloud.png")

        wc = WordCloud(
            width=1000, height=500,
            background_color="#ffffff",
            colormap="YlOrRd",
            max_words=80,
            min_font_size=10,
            font_path=None,
            collocations=False,
        ).generate_from_frequencies(topic_weights)

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title("热门 Topics 词云（按星数加权）", fontsize=14, fontweight="bold")
        plt.tight_layout()
        return self._save_fig(fig, "07_topics_wordcloud.png")

    def chart_activity_scores(self, analyzer=None) -> str:
        """仓库活跃度评分 TOP15 横向柱状图。"""
        from analyze import GitHubAnalyzer
        if analyzer is None:
            analyzer = GitHubAnalyzer(self.df)
        scores = analyzer.activity_scores()
        n = min(len(scores), 15)
        topn = scores.head(n).iloc[::-1]  # 反转让最高分在顶部

        fig, ax = plt.subplots(figsize=(12, 7))
        colors = []
        for v in topn["activity_score"]:
            if v >= 70:
                colors.append("#2dba4e")
            elif v >= 40:
                colors.append("#f0ad4e")
            else:
                colors.append("#d9534f")

        bars = ax.barh(
            range(n), topn["activity_score"].values,
            color=colors, edgecolor="#333",
        )
        ax.set_yticks(range(n))
        labels = topn["name"].apply(lambda s: s[:25] + "..." if len(s) > 25 else s)
        ax.set_yticklabels(labels.values, fontsize=9)
        ax.set_xlabel("活跃度评分 (0-100)", fontsize=12)
        ax.set_title("仓库活跃度评分 TOP15", fontsize=14, fontweight="bold")
        ax.set_xlim(0, 105)
        ax.axvline(x=70, color="#2dba4e", linestyle="--", alpha=0.4, label="高活跃 (70)")
        ax.axvline(x=40, color="#f0ad4e", linestyle="--", alpha=0.4, label="中活跃 (40)")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(axis="x", alpha=0.3)

        for bar, val in zip(bars, topn["activity_score"].values):
            ax.text(
                bar.get_width() + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}", va="center", fontsize=8,
            )

        plt.tight_layout()
        return self._save_fig(fig, "08_activity_scores.png")

    def chart_language_radar(self, analyzer=None) -> str:
        """语言偏好雷达图 — 按年份展示语言变化趋势。"""
        from analyze import GitHubAnalyzer
        if analyzer is None:
            analyzer = GitHubAnalyzer(self.df)
        trend = analyzer.language_trend_by_year()
        if trend.empty or len(trend.columns) < 3:
            # 数据不足，返回一个空图
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.text(0.5, 0.5, "数据不足，无法生成雷达图\n（需要至少 3 种语言 + 2 个年份）",
                    ha="center", va="center", fontsize=14, color="#8b8b8b")
            ax.axis("off")
            plt.tight_layout()
            return self._save_fig(fig, "09_language_radar.png")

        # 取最近的几年（最多 5 年）
        years = sorted(trend.index)[-5:]
        langs = list(trend.columns)
        n_langs = len(langs)
        n_years = len(years)

        # 角度
        angles = np.linspace(0, 2 * np.pi, n_langs, endpoint=False).tolist()
        angles += angles[:1]  # 闭合

        fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
        colors = plt.cm.Set2(np.linspace(0, 1, n_years))

        for i, year in enumerate(years):
            values = trend.loc[year].values.tolist()
            values += values[:1]  # 闭合
            ax.plot(angles, values, "o-", linewidth=2, label=str(int(year)),
                    color=colors[i], markersize=5)
            ax.fill(angles, values, alpha=0.1, color=colors[i])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(langs, fontsize=11)
        ax.set_title("语言偏好趋势（按年份）", fontsize=14, fontweight="bold", pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)

        plt.tight_layout()
        return self._save_fig(fig, "09_language_radar.png")

    def generate_all(self) -> list[str]:
        """生成所有图表，返回路径列表。"""
        print("\n  正在生成图表...")
        paths: list[str] = []
        for method in [
            self.chart_top_stars,
            self.chart_language_pie,
            self.chart_stars_vs_forks,
            self.chart_creation_timeline,
            self.chart_stars_histogram,
            self.chart_language_stars,
            self.chart_topics_wordcloud,
            self.chart_activity_scores,
            self.chart_language_radar,
            self.chart_cluster_scatter,
            self.chart_regression_comparison,
        ]:
            try:
                path = method()
                print(f"    [OK] {os.path.basename(path)}")
                paths.append(path)
            except Exception as e:
                print(f"    [FAIL] {method.__name__}: {e}")
        return paths

    # ── 数据建模图表 ──────────────────────────────────────────

    def chart_cluster_scatter(self, analyzer=None) -> str:
        """仓库聚类分析散点图 — Stars vs Forks，按聚类着色。"""
        from analyze import GitHubAnalyzer
        if analyzer is None:
            analyzer = GitHubAnalyzer(self.df)
        try:
            result = analyzer.cluster_repos(n_clusters=4)
        except ValueError:
            # 数据不足时生成占位图
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.text(0.5, 0.5, "数据量不足，无法进行聚类分析\n（需要至少 5 个仓库）",
                    ha="center", va="center", fontsize=14, color="#8b8b8b")
            ax.axis("off")
            plt.tight_layout()
            return self._save_fig(fig, "10_cluster_scatter.png")

        df = analyzer.df.copy()
        labels = result["labels"]
        cluster_names = result["cluster_names"]
        colors_list = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"]

        fig, ax = plt.subplots(figsize=(12, 8))

        for c in range(result["n_clusters"]):
            mask = labels == c
            name = cluster_names.get(c, {}).get("name", f"聚类 {c}")
            count = cluster_names.get(c, {}).get("count", 0)
            color = colors_list[c % len(colors_list)]

            # 使用对数坐标散点
            x = df.loc[mask, "stars"].values.astype(float) + 1
            y = df.loc[mask, "forks"].values.astype(float) + 1
            ax.scatter(x, y, c=color, s=60, alpha=0.7, edgecolors="white",
                       linewidth=0.5, label=f"{name} ({count})")

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Stars (log scale)", fontsize=12)
        ax.set_ylabel("Forks (log scale)", fontsize=12)
        ax.set_title("仓库聚类分析 — K-Means (K=4)", fontsize=14, fontweight="bold")
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(alpha=0.3)

        # 标注最高星仓库
        top_idx = df["stars"].idxmax()
        top_row = df.loc[top_idx]
        ax.annotate(
            top_row["name"][:18],
            (top_row["stars"] + 1, top_row["forks"] + 1),
            fontsize=8, arrowprops=dict(arrowstyle="->", color="gray"),
        )

        # 添加轮廓系数
        sil = result.get("silhouette_score")
        if sil is not None:
            ax.text(0.98, 0.02, f"轮廓系数: {sil:.4f}",
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=9, color="#666", style="italic")

        plt.tight_layout()
        return self._save_fig(fig, "10_cluster_scatter.png")

    def chart_regression_comparison(self, analyzer=None) -> str:
        """回归模型对比图 — 线性回归 vs 随机森林，实际值 vs 预测值。"""
        from analyze import GitHubAnalyzer
        if analyzer is None:
            analyzer = GitHubAnalyzer(self.df)
        try:
            result = analyzer.regression_predict()
        except ValueError:
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.text(0.5, 0.5, "数据量不足，无法进行回归建模\n（需要至少 10 个仓库）",
                    ha="center", va="center", fontsize=14, color="#8b8b8b")
            ax.axis("off")
            plt.tight_layout()
            return self._save_fig(fig, "11_regression_comparison.png")

        metrics = result["metrics"]

        fig, axes = plt.subplots(1, 2, figsize=(16, 7))

        for idx, (model_name, data) in enumerate(metrics.items()):
            ax = axes[idx]
            actuals = np.array(data["actuals"][:20])
            predictions = np.array(data["predictions"][:20])

            ax.scatter(actuals, predictions, alpha=0.7, s=50,
                       color="#3498db" if idx == 0 else "#2ecc71",
                       edgecolors="white", linewidth=0.5)

            # 理想线 y=x
            max_val = max(actuals.max(), predictions.max()) * 1.1
            ax.plot([0, max_val], [0, max_val], "r--", linewidth=1.5,
                    alpha=0.7, label="理想预测 (y=x)")

            ax.set_xlabel("实际 Stars", fontsize=12)
            ax.set_ylabel("预测 Stars", fontsize=12)
            r2 = data["R2"]
            mae = data["MAE"]
            rmse = data["RMSE"]
            ax.set_title(f"{model_name}\nR²={r2:.4f}  MAE={mae:.0f}  RMSE={rmse:.0f}",
                         fontsize=12, fontweight="bold")
            ax.legend(fontsize=9)
            ax.grid(alpha=0.3)

            # 标注点的数量
            n_total = result["train_size"] + result["test_size"]
            ax.text(0.02, 0.98, f"训练集: {result['train_size']}  测试集: {result['test_size']}\n总样本: {n_total}",
                    transform=ax.transAxes, va="top", fontsize=8, color="#666")

        fig.suptitle("Stars 预测回归模型对比 — 实际值 vs 预测值",
                     fontsize=14, fontweight="bold", y=1.02)
        plt.tight_layout()
        return self._save_fig(fig, "11_regression_comparison.png")
