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
  7. 仓库聚类分析（K-Means）
  8. Stars 预测回归模型（线性回归 + 随机森林）
"""

import re

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    r2_score,
    mean_absolute_error,
    mean_squared_error,
)


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
        a("【九、聚类分析】")
        try:
            cluster_result = self.cluster_repos()
            for label, info in cluster_result["cluster_names"].items():
                a(f"  聚类 {label}: {info['name']} ({info['count']} 个仓库)")
        except Exception:
            a("  (数据不足，无法聚类)")
        a("")
        a("【十、Stars 预测回归模型】")
        try:
            reg_result = self.regression_predict()
            for model_name, metrics in reg_result["metrics"].items():
                a(f"  {model_name}: R²={metrics['R2']:.4f}, MAE={metrics['MAE']:.2f}, RMSE={metrics['RMSE']:.2f}")
        except Exception:
            a("  (数据不足，无法建模)")
        a("")
        a("=" * 60)

        return "\n".join(lines)

    # ── 数据建模接口 ────────────────────────────────────────

    def cluster_repos(self, n_clusters: int = 4) -> dict:
        """对仓库进行 K-Means 聚类分析。

        使用 Stars、Forks、Open Issues、仓库年龄（天）、
        Stars/天 五个维度特征，对仓库进行聚类，
        识别不同类型的仓库群体。

        Args:
            n_clusters: 聚类数量，默认 4 类。

        Returns:
            dict: 包含聚类标签、聚类中心、聚类名称等信息。
        """
        features = ["stars", "forks", "open_issues", "age_days", "stars_per_day"]
        available = [f for f in features if f in self.df.columns]
        if len(available) < 2 or len(self.df) < n_clusters + 1:
            raise ValueError("数据量不足，无法进行聚类分析")

        X = self.df[available].copy()
        # 替换无穷大和 NaN
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        self.df["cluster"] = labels

        # 分析每个聚类的特征
        cluster_stats = {}
        cluster_names = {}
        name_map = {0: "普通仓库", 1: "潜力仓库", 2: "热门仓库", 3: "超级仓库"}
        for c in range(n_clusters):
            mask = labels == c
            cluster_df = self.df[mask]
            stats = {
                "count": int(mask.sum()),
                "avg_stars": round(cluster_df["stars"].mean(), 1),
                "avg_forks": round(cluster_df["forks"].mean(), 1),
                "avg_age_days": round(cluster_df["age_days"].mean(), 1) if "age_days" in cluster_df.columns else 0,
                "avg_stars_per_day": round(cluster_df["stars_per_day"].mean(), 3) if "stars_per_day" in cluster_df.columns else 0,
                "repos": cluster_df["name"].tolist()[:5],
            }
            cluster_stats[c] = stats

            # 自动生成聚类名称
            avg_s = stats["avg_stars"]
            avg_spd = stats["avg_stars_per_day"]
            if avg_s > 1000:
                cluster_names[c] = {"name": "超级热门仓库 (Stars>1000)", **stats}
            elif avg_s > 100:
                cluster_names[c] = {"name": "高影响力仓库 (Stars 100-1000)", **stats}
            elif avg_spd > 1:
                cluster_names[c] = {"name": "快速增长仓库 (日均>1 star)", **stats}
            else:
                cluster_names[c] = {"name": "普通/入门仓库", **stats}

        # 聚类中心
        centers = pd.DataFrame(
            scaler.inverse_transform(kmeans.cluster_centers_),
            columns=available,
        ).round(2)

        return {
            "labels": labels,
            "centers": centers,
            "cluster_stats": cluster_stats,
            "cluster_names": cluster_names,
            "n_clusters": n_clusters,
            "features": available,
            "silhouette_score": round(
                float(__import__("sklearn.metrics", fromlist=["silhouette_score"]).silhouette_score(X_scaled, labels)),
                4,
            ) if len(self.df) > n_clusters else None,
        }

    def regression_predict(self) -> dict:
        """使用线性回归和随机森林预测仓库 Stars 数。

        特征: Forks, Open Issues, 仓库年龄(天), Stars/天, Fork比率

        Returns:
            dict: 包含模型评估指标和特征重要性。
        """
        features = ["forks", "open_issues", "age_days", "stars_per_day", "fork_ratio"]
        available = [f for f in features if f in self.df.columns]
        if len(available) < 2 or len(self.df) < 10:
            raise ValueError("数据量不足，无法进行回归建模")

        X = self.df[available].copy()
        y = self.df["stars"].copy()

        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        y = y.replace([np.inf, -np.inf], np.nan).fillna(0)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42
        )

        results = {}

        # 线性回归
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        y_pred_lr = lr.predict(X_test)
        results["线性回归"] = {
            "R2": round(r2_score(y_test, y_pred_lr), 4),
            "MAE": round(mean_absolute_error(y_test, y_pred_lr), 2),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_test, y_pred_lr))), 2),
            "coefficients": dict(zip(available, lr.coef_.round(4).tolist())),
            "intercept": round(float(lr.intercept_), 4),
            "predictions": y_pred_lr.round(0).tolist()[:20],
            "actuals": y_test.values.tolist()[:20],
        }

        # 随机森林
        rf = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
        rf.fit(X_train, y_train)
        y_pred_rf = rf.predict(X_test)
        results["随机森林"] = {
            "R2": round(r2_score(y_test, y_pred_rf), 4),
            "MAE": round(mean_absolute_error(y_test, y_pred_rf), 2),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_test, y_pred_rf))), 2),
            "feature_importance": dict(zip(available, rf.feature_importances_.round(4).tolist())),
            "predictions": y_pred_rf.round(0).tolist()[:20],
            "actuals": y_test.values.tolist()[:20],
        }

        return {
            "metrics": results,
            "features": available,
            "train_size": len(X_train),
            "test_size": len(X_test),
        }
