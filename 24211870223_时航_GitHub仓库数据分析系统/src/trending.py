from __future__ import annotations

"""
GitHub Trending 热门项目采集模块
通过 GitHub Search API 获取各时间段内最热门的新仓库。

时间范围：每日 / 每周 / 每月
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from github_api import BaseGitHubSession, resolve_token


class TrendingScraper(BaseGitHubSession):
    """通过 GitHub Search API 获取热门新仓库。"""

    def __init__(self, token: str = "") -> None:
        super().__init__(token=token)

    def _search(self, query: str, max_items: int = 30) -> List[Dict[str, Any]]:
        """搜索仓库，返回结构化数据。"""
        import time
        time.sleep(0.7)  # Search API 需要更长间隔

        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_items, 30),
            "page": 1,
        }
        data = self._get(
            "https://api.github.com/search/repositories",
            params=params,
        )
        items = data.get("items", [])

        results: List[Dict[str, Any]] = []
        for item in items:
            lic = item.get("license") or {}
            results.append({
                "name": item["name"],
                "full_name": item["full_name"],
                "description": (item.get("description") or "")[:200],
                "html_url": item["html_url"],
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "language": item.get("language") or "Other",
                "topics": ",".join(item.get("topics", [])),
                "created_at": item.get("created_at", ""),
                "owner": item.get("owner", {}).get("login", ""),
                "owner_avatar": item.get("owner", {}).get("avatar_url", ""),
            })
        return results

    def daily(self, max_items: int = 25) -> List[Dict[str, Any]]:
        """今日热门新仓库（过去 24 小时内创建）。"""
        since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        return self._search(f"created:>={since}", max_items=max_items)

    def weekly(self, max_items: int = 25) -> List[Dict[str, Any]]:
        """本周热门新仓库（过去 7 天内创建）。"""
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        return self._search(f"created:>={since}", max_items=max_items)

    def monthly(self, max_items: int = 25) -> List[Dict[str, Any]]:
        """本月热门新仓库（过去 30 天内创建）。"""
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        return self._search(f"created:>={since}", max_items=max_items)

    def by_language(self, language: str, period: str = "weekly",
                    max_items: int = 20) -> List[Dict[str, Any]]:
        """按语言筛选某时间段的热门仓库。"""
        days = {"daily": 1, "weekly": 7, "monthly": 30}
        d = days.get(period, 7)
        since = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%d")
        return self._search(
            f"language:{language} created:>={since}",
            max_items=max_items,
        )
