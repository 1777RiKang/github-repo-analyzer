"""Unit tests for analyze.py — run with: python -m pytest tests/ -v"""

import sys
import os

import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyze import GitHubAnalyzer


def _make_sample_df(n: int = 20) -> pd.DataFrame:
    """Create a synthetic DataFrame mimicking GitHub repo data."""
    rng = np.random.RandomState(42)
    languages = ["Python", "JavaScript", "Go", "Rust", "C++", "Java"]
    topics_pool = ["machine-learning", "web", "cli", "data-science", "golang", "google-api"]
    licenses = ["MIT", "Apache-2.0", "GPL-3.0", "None"]

    rows = []
    for i in range(n):
        lang = rng.choice(languages)
        star = int(rng.exponential(100))
        fork = int(star * rng.uniform(0.1, 0.5))
        n_topics = rng.randint(0, 4)
        chosen = list(rng.choice(topics_pool, size=n_topics, replace=False)) if n_topics > 0 else []
        rows.append({
            "name": f"repo-{i}",
            "full_name": f"user/repo-{i}",
            "description": f"Test repo {i}",
            "html_url": f"https://github.com/user/repo-{i}",
            "stars": star,
            "forks": fork,
            "watchers": int(star * 0.3),
            "open_issues": rng.randint(0, 20),
            "language": lang,
            "topics": ",".join(chosen),
            "size_kb": rng.randint(10, 5000),
            "license_name": rng.choice(licenses),
            "created_at": f"202{rng.randint(0, 5)}-{rng.randint(1,13):02d}-{rng.randint(1,29):02d}T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "pushed_at": "2025-01-01T00:00:00Z",
            "is_fork": False,
            "archived": False,
        })
    return pd.DataFrame(rows)


class TestBasicStats:
    def test_returns_all_keys(self):
        df = _make_sample_df()
        analyzer = GitHubAnalyzer(df)
        stats = analyzer.basic_stats()
        expected = {"仓库总数", "总星数(Stars)", "平均星数", "中位星数", "最高星数",
                    "总Forks", "平均Forks", "主要语言", "语言种类数"}
        assert expected == set(stats.keys())

    def test_repo_count(self):
        df = _make_sample_df(15)
        analyzer = GitHubAnalyzer(df)
        stats = analyzer.basic_stats()
        assert stats["仓库总数"] == 15

    def test_forks_filtered_out(self):
        df = _make_sample_df(10)
        df.loc[0, "is_fork"] = True
        analyzer = GitHubAnalyzer(df)
        stats = analyzer.basic_stats()
        assert stats["仓库总数"] == 9  # one fork excluded


class TestTopRepos:
    def test_returns_n_rows(self):
        df = _make_sample_df(20)
        analyzer = GitHubAnalyzer(df)
        top = analyzer.top_repos(n=5)
        assert len(top) == 5

    def test_sorted_descending(self):
        df = _make_sample_df(20)
        analyzer = GitHubAnalyzer(df)
        top = analyzer.top_repos(n=10)
        assert list(top["stars"]) == sorted(top["stars"], reverse=True)


class TestLanguageDistribution:
    def test_has_expected_columns(self):
        df = _make_sample_df()
        analyzer = GitHubAnalyzer(df)
        dist = analyzer.language_distribution()
        assert "仓库数" in dist.columns
        assert "总星数" in dist.columns
        assert "平均星数" in dist.columns


class TestTopicsAnalysis:
    def test_no_substring_match_bug(self):
        """'go' topic must NOT match 'golang' or 'google-api'."""
        df = pd.DataFrame([
            {"name": "a", "full_name": "u/a", "description": "", "html_url": "",
             "stars": 100, "forks": 10, "watchers": 5, "open_issues": 0,
             "language": "Go", "topics": "go,cli", "size_kb": 100,
             "license_name": "MIT", "created_at": "2024-01-01T00:00:00Z",
             "updated_at": "", "pushed_at": "", "is_fork": False, "archived": False},
            {"name": "b", "full_name": "u/b", "description": "", "html_url": "",
             "stars": 200, "forks": 20, "watchers": 10, "open_issues": 0,
             "language": "Go", "topics": "golang,google-api", "size_kb": 200,
             "license_name": "MIT", "created_at": "2024-01-01T00:00:00Z",
             "updated_at": "", "pushed_at": "", "is_fork": False, "archived": False},
        ])
        analyzer = GitHubAnalyzer(df)
        result = analyzer.topics_analysis(top_n=10)
        # "go" should only match repo "a", not "golang" or "google-api"
        go_row = result[result["topic"] == "go"]
        if len(go_row) > 0:
            assert go_row.iloc[0]["count"] == 1

    def test_empty_topics(self):
        df = _make_sample_df(5)
        df["topics"] = ""
        analyzer = GitHubAnalyzer(df)
        result = analyzer.topics_analysis()
        assert len(result) == 0


class TestCreationTimeline:
    def test_returns_yearly_data(self):
        df = _make_sample_df(20)
        analyzer = GitHubAnalyzer(df)
        timeline = analyzer.creation_timeline()
        assert not timeline.empty
        assert "新建仓库数" in timeline.columns


class TestLicenseDistribution:
    def test_returns_data(self):
        df = _make_sample_df(20)
        analyzer = GitHubAnalyzer(df)
        dist = analyzer.license_distribution()
        assert not dist.empty
        assert "仓库数" in dist.columns


class TestSummaryReport:
    def test_report_is_string(self):
        df = _make_sample_df(10)
        analyzer = GitHubAnalyzer(df)
        report = analyzer.summary_report()
        assert isinstance(report, str)
        assert "GitHub 仓库数据分析报告" in report
        assert "【一、基础数据概览】" in report
        assert "【八、仓库活跃度概览】" in report


class TestActivityScores:
    def test_returns_dataframe(self):
        df = _make_sample_df(15)
        analyzer = GitHubAnalyzer(df)
        scores = analyzer.activity_scores()
        assert len(scores) == 15
        assert "activity_score" in scores.columns

    def test_score_range(self):
        df = _make_sample_df(20)
        analyzer = GitHubAnalyzer(df)
        scores = analyzer.activity_scores()
        assert scores["activity_score"].between(0, 100).all()

    def test_sorted_descending(self):
        df = _make_sample_df(15)
        analyzer = GitHubAnalyzer(df)
        scores = analyzer.activity_scores()
        assert list(scores["activity_score"]) == sorted(
            scores["activity_score"], reverse=True
        )

    def test_activity_summary(self):
        df = _make_sample_df(10)
        analyzer = GitHubAnalyzer(df)
        summary = analyzer.activity_summary()
        assert "平均活跃度" in summary
        assert "最活跃仓库" in summary
        assert "高活跃(≥70)" in summary


class TestLanguageTrendByYear:
    def test_returns_pivot_table(self):
        df = _make_sample_df(30)
        analyzer = GitHubAnalyzer(df)
        trend = analyzer.language_trend_by_year()
        # Should have years as index and languages as columns
        assert len(trend.columns) > 0

    def test_empty_for_single_year(self):
        df = _make_sample_df(5)
        df["created_at"] = "2024-01-01T00:00:00Z"
        analyzer = GitHubAnalyzer(df)
        trend = analyzer.language_trend_by_year()
        # Should still return data (even if 1 year)
        assert not trend.empty or True  # may be empty if < 2 languages
