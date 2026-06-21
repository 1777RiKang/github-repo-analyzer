"""
数据分析模块
基于 GitHub 仓库数据，使用 Pandas 进行多维度统计分析。

分析维度：
  1. 基础统计：总仓库数、总星数、平均星数等
  2. 编程语言分布与语言受欢迎度
  3. Stars 与 Forks 相关性
  4. 仓库创建时间趋势
  5. 主题标签(Topics)词频
  6. 许可证分布
"""

import re

import pandas as pd
import numpy as np


class GitHubAnalyzer:
    """GitHub 仓库数据分析器。"""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self._preprocess()

    def _preprocess(self) -> None:
        """数据预处理。"""
        # 过滤 fork 和 archived 仓库（可选）
        self.df_original = self.df.copy()
        self.df = self.df[self.df["is_fork"] == False]

        # 时间字段
        for col in ["created_at", "updated_at", "pushed_at"]:
            if col in self.df.columns:
                self.df[col + "_dt"] = pd.to_datetime(
                    self.df[col], errors="coerce"
                )

        # 创建年份/月份
        if "created_at_dt" in self.df.columns:
            self.df["created_year"] = self.df["created_at_dt"].dt.year
            self.df["created_month"] = self.df["created_at_dt"].dt.to_period("M")

        # 仓库年龄（天）
        if "created_at_dt" in self.df.columns:
            now = pd.Timestamp.now(tz="UTC")
            self.df["age_days"] = (now - self.df["created_at_dt"]).dt.days

        # 星数/年龄比率（日均增长）
        self.df["stars_per_day"] = np.where(
            self.df["age_days"] > 0,
            self.df["stars"] / self.df["age_days"],
            0.0,
        )

        # Forks/Stars 比率
        self.df["fork_ratio"] = np.where(
            self.df["stars"] > 0,
            self.df["forks"] / self.df["stars"],
            0.0,
        )

    # ── 分析接口 ──────────────────────────────────────────

    def basic_stats(self) -> dict:
        """基础描述性统计。"""
        s = self.df["stars"]
        f = self.df["forks"]
        return {
            "仓库总数": len(self.df),
            "总星数(Stars)": int(s.sum()),
            "平均星数": int(s.mean()),
            "中位星数": int(s.median()),
            "最高星数": int(s.max()),
            "总Forks": int(f.sum()),
            "平均Forks": int(f.mean()),
            "主要语言": self.df["language"].mode().iloc[0]
            if len(self.df["language"].mode()) > 0
            else "N/A",
            "语言种类数": self.df["language"].nunique(),
        }

    def top_repos(self, by: str = "stars", n: int = 10) -> pd.DataFrame:
        """获取排行前 N 的仓库。"""
        cols = [
            "name", "language", "stars", "forks", "open_issues",
            "stars_per_day", "created_at",
        ]
        return self.df.nlargest(n, by)[cols]

    def language_distribution(self) -> pd.DataFrame:
        """编程语言分布统计。"""
        grouped = self.df.groupby("language").agg(
            仓库数=("name", "count"),
            总星数=("stars", "sum"),
            平均星数=("stars", "mean"),
            中位星数=("stars", "median"),
        ).sort_values("仓库数", ascending=False)
        return grouped.round(1)

    def language_top_stars(self, top_n: int = 15) -> pd.DataFrame:
        """按语言的平均星数排行。"""
        grouped = self.df.groupby("language").agg(
            仓库数=("name", "count"),
            平均星数=("stars", "mean"),
            最高星数=("stars", "max"),
        )
        # 过滤仓库数太少的语言
        grouped = grouped[grouped["仓库数"] >= 2]
        return grouped.nlargest(top_n, "平均星数").round(1)

    def stars_forks_correlation(self) -> pd.DataFrame:
        """Stars 与 Forks 的相关性（分段聚合）。"""
        bins = [0, 10, 50, 100, 500, 1000, 5000, 9999999]
        labels = ["<10", "10-50", "50-100", "100-500", "500-1K", "1K-5K", "5K+"]
        self.df["star_bin"] = pd.cut(
            self.df["stars"], bins=bins, labels=labels
        )
        grouped = self.df.groupby("star_bin", observed=False).agg(
            仓库数=("name", "count"),
            平均Forks=("forks", "mean"),
            平均Issues=("open_issues", "mean"),
        )
        return grouped.round(1)

    def creation_timeline(self) -> pd.DataFrame:
        """仓库创建时间趋势（按年/月）。"""
        if "created_year" not in self.df.columns:
            return pd.DataFrame()
        yearly = self.df.groupby("created_year").agg(
            新建仓库数=("name", "count"),
            累计星数=("stars", "sum"),
            平均星数=("stars", "mean"),
        )
        return yearly

    def topics_analysis(self, top_n: int = 20) -> pd.DataFrame:
        """主题标签(Topics)词频分析。"""
        all_topics: list[str] = []
        for t in self.df["topics"].dropna():
            if t:
                all_topics.extend(t.split(","))
        if not all_topics:
            return pd.DataFrame(columns=["topic", "count", "avg_stars"])
        topic_series = pd.Series(all_topics)
        counts = topic_series.value_counts().head(top_n)
        # 计算每个 topic 的平均星数（精确匹配，避免 "go" 匹配 "google"）
        result_rows: list[dict] = []
        for topic in counts.index:
            pattern = r"(?:^|,)" + re.escape(topic) + r"(?:,|$)"
            mask = self.df["topics"].str.contains(pattern, na=False, regex=True)
            avg_stars = self.df.loc[mask, "stars"].mean()
            result_rows.append({
                "topic": topic,
                "count": counts[topic],
                "avg_stars": round(avg_stars, 1),
            })
        return pd.DataFrame(result_rows)

    def license_distribution(self) -> pd.DataFrame:
        """许可证分布。"""
        grouped = self.df.groupby("license_name").agg(
            仓库数=("name", "count"), 平均星数=("stars", "mean")
        ).sort_values("仓库数", ascending=False)
        # 合并罕见的许可证为 "Other"
        top = grouped.head(10)
        other_count = grouped.iloc[10:]["仓库数"].sum() if len(grouped) > 10 else 0
        if other_count > 0:
            top.loc["Other"] = [other_count, grouped.iloc[10:]["平均星数"].mean()]
        return top.round(1)

    def activity_scores(self) -> pd.DataFrame:
        """仓库活跃度评分（0-100）。

        评分维度:
          - push 活跃度 (40%): 最近推送越近分越高
          - 星数影响力 (20%): 相对用户最高星数归一化
          - Fork 比率 (15%): 0.1-0.5 为理想区间
          - Issue 管理 (15%): open_issues / stars 比率越低越好
          - 非归档 (10%): archived = False 得满分
        """
        df = self.df.copy()
        now = pd.Timestamp.now(tz="UTC")

        # 1. push 活跃度 (40%)
        if "pushed_at_dt" in df.columns:
            days_since_push = (now - df["pushed_at_dt"]).dt.days.fillna(9999)
        elif "pushed_at" in df.columns:
            pushed = pd.to_datetime(df["pushed_at"], errors="coerce", utc=True)
            days_since_push = (now - pushed).dt.days.fillna(9999)
        else:
            days_since_push = pd.Series(9999, index=df.index)

        # 指数衰减: 30天内满分, 180天约50%, 365天约25%
        push_score = 100 * np.exp(-days_since_push / 180)
        push_score = push_score.clip(0, 100)

        # 2. 星数影响力 (20%) — 相对归一化
        max_stars = df["stars"].max()
        if max_stars > 0:
            star_score = (df["stars"] / max_stars) * 100
        else:
            star_score = pd.Series(0, index=df.index)

        # 3. Fork 比率 (15%) — 0.1~0.5 区间满分，过高或过低扣分
        ratio = df["fork_ratio"]
        fork_score = pd.Series(0.0, index=df.index)
        fork_score = np.where(ratio < 0.1, ratio / 0.1 * 100,
                     np.where(ratio <= 0.5, 100,
                     np.where(ratio <= 1.0, 100 - (ratio - 0.5) / 0.5 * 50, 50)))

        # 4. Issue 管理 (15%) — issues/stars 比率越低越好
        issue_ratio = np.where(
            df["stars"] > 0,
            df["open_issues"] / df["stars"],
            df["open_issues"] / 1.0,
        )
        issue_score = np.clip(100 - issue_ratio * 200, 0, 100)

        # 5. 非归档 (10%)
        archived_score = np.where(df["archived"] == True, 0, 100).astype(float)

        # 加权求和
        total = (
            push_score * 0.40
            + star_score * 0.20
            + fork_score * 0.15
            + issue_score * 0.15
            + archived_score * 0.10
        )

        result = df[["name", "language", "stars", "forks"]].copy()
        result["activity_score"] = np.round(total, 1)
        result["push_score"] = np.round(push_score, 1)
        result["star_score"] = np.round(star_score, 1)
        return result.sort_values("activity_score", ascending=False).reset_index(drop=True)

    def activity_summary(self) -> dict:
        """活跃度概览统计。"""
        scores = self.activity_scores()
        return {
            "平均活跃度": round(scores["activity_score"].mean(), 1),
            "最活跃仓库": scores.iloc[0]["name"] if len(scores) > 0 else "N/A",
            "最活跃得分": round(scores.iloc[0]["activity_score"], 1) if len(scores) > 0 else 0,
            "高活跃(≥70)": int((scores["activity_score"] >= 70).sum()),
            "中活跃(40-69)": int(((scores["activity_score"] >= 40) & (scores["activity_score"] < 70)).sum()),
            "低活跃(<40)": int((scores["activity_score"] < 40).sum()),
        }

    def language_trend_by_year(self) -> pd.DataFrame:
        """按年份统计语言偏好变化，用于绘制雷达图。

        返回: DataFrame, index=年份, columns=语言, values=仓库数
        """
        if "created_year" not in self.df.columns:
            return pd.DataFrame()
        # 取仓库数最多的 TOP6 语言
        top_langs = self.df["language"].value_counts().head(6).index.tolist()
        df_top = self.df[self.df["language"].isin(top_langs)]
        pivot = df_top.pivot_table(
            index="created_year", columns="language",
            values="name", aggfunc="count", fill_value=0,
        )
        return pivot

    def summary_report(self) -> str:
        """生成完整分析报告文本。"""
        stats = self.basic_stats()
        top = self.top_repos(n=5)
        lang = self.language_distribution().head(10)
        top_lang = self.language_top_stars(8)
        timeline = self.creation_timeline()
        topics = self.topics_analysis(10)
        licenses = self.license_distribution()

        lines: list[str] = []
        a = lines.append
        a("=" * 60)
        a("  GitHub 仓库数据分析报告")
        a("=" * 60)
        a("")
        a("【一、基础数据概览】")
        for k, v in stats.items():
            a(f"  {k}: {v}")
        a("")
        a("【二、Stars TOP5 仓库】")
        a(top.to_string(index=False))
        a("")
        a("【三、编程语言分布 (Top 10)】")
        a(lang.to_string())
        a("")
        a("【四、语言平均星数排行 (Top 8)】")
        a(top_lang.to_string())
        a("")
        a("【五、仓库创建时间趋势】")
        a(timeline.to_string() if not timeline.empty else "  (无数据)")
        a("")
        a("【六、热门主题标签 (Top 10)】")
        a(topics.to_string(index=False) if not topics.empty else "  (无数据)")
        a("")
        a("【七、许可证分布】")
        a(licenses.to_string())
        a("")
        a("【八、仓库活跃度概览】")
        act = self.activity_summary()
        for k, v in act.items():
            a(f"  {k}: {v}")
        a("")
        a("=" * 60)

        return "\n".join(lines)

    def project_health(self, include_forks: bool = False) -> dict:
        """项目健康度分析：统计 Issues/Wiki/Pages/Discussions 开启率。"""
        df = self.df if not include_forks else self.df_original
        total = len(df)
        if total == 0:
            return {}
        def _safe_sum(field):
            return int(df[field].sum()) if field in df.columns else 0
        def _safe_mean(field):
            return df[field].mean() if field in df.columns else 0.0
        def _safe_count(field):
            return int((df[field] != "").sum()) if field in df.columns else 0
        def _safe_count_mean(field):
            return (df[field] != "").mean() if field in df.columns else 0.0
        return {
            "总仓库数": total,
            "Issues 开启": f"{_safe_sum('has_issues')} ({_safe_mean('has_issues'):.1%})" if "has_issues" in df.columns else "N/A",
            "Wiki 开启": f"{_safe_sum('has_wiki')} ({_safe_mean('has_wiki'):.1%})" if "has_wiki" in df.columns else "N/A",
            "Pages 开启": f"{_safe_sum('has_pages')} ({_safe_mean('has_pages'):.1%})" if "has_pages" in df.columns else "N/A",
            "Discussions 开启": f"{_safe_sum('has_discussions')} ({_safe_mean('has_discussions'):.1%})" if "has_discussions" in df.columns else "N/A",
            "有主页仓库": f"{_safe_count('homepage')} ({_safe_count_mean('homepage'):.1%})" if "homepage" in df.columns else "N/A",
        }

    def repo_completeness(self) -> pd.DataFrame:
        """仓库完整度评分 (0-5)：每个开启的功能 +1 分。"""
        avail_cols = ["name", "full_name", "language", "stars"]
        extra = ["has_issues", "has_wiki", "has_pages", "has_discussions", "homepage"]
        for c in extra:
            if c not in self.df.columns:
                self.df[c] = False if c != "homepage" else ""
        df = self.df[avail_cols + extra].copy()
        df["completeness_score"] = (
            df["has_issues"].astype(int) +
            df["has_wiki"].astype(int) +
            df["has_pages"].astype(int) +
            df["has_discussions"].astype(int) +
            (df["homepage"] != "").astype(int)
        )
        return df.sort_values("completeness_score", ascending=False)
