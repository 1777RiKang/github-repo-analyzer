from __future__ import annotations

"""
GitHub 数据采集模块
通过 GitHub REST API (v3) 获取用户/组织的仓库数据。

采集数据字段：
  - 仓库名、描述、语言、主题标签
  - Stars、Forks、Watchers、Open Issues
  - 仓库大小(KB)、许可证
  - 创建时间、更新时间、推送时间

API 限制：未认证 60次/小时，认证后 5000次/小时
"""

import os
import time
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.github.com"
HEADERS = {
    "User-Agent": "github-repo-analyzer/1.0",
    "Accept": "application/vnd.github.v3+json",
}

REQUEST_DELAY = 0.5  # 请求间隔（秒），避免触发限流
MAX_RETRIES = 3


def resolve_token(token: str = "") -> str:
    """Resolve a GitHub token: explicit arg > env var GITHUB_TOKEN."""
    token = (token or "").strip()
    if token:
        return token
    return os.environ.get("GITHUB_TOKEN", "").strip()


class BaseGitHubSession:
    """Shared HTTP session with token and rate-limit handling."""

    def __init__(self, token: str = "") -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        resolved = resolve_token(token)
        if resolved:
            self.session.headers["Authorization"] = f"token {resolved}"

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET 请求，带重试和限流处理。"""
        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(REQUEST_DELAY)
                resp = self.session.get(url, params=params, timeout=20)

                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    remaining = resp.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        reset_at = int(resp.headers.get("X-RateLimit-Reset", 0))
                        wait = max(reset_at - int(time.time()), 60)
                        raise RuntimeError(
                            f"API 限流已达上限，需等待约 {wait // 60} 分钟"
                        )

                if resp.status_code == 404:
                    raise RuntimeError("用户或组织不存在 (HTTP 404)")

                resp.raise_for_status()
                return resp.json()

            except requests.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        raise RuntimeError(str(last_error))

    def _get_paginated(
        self, url: str, params: Optional[Dict[str, Any]] = None, max_items: int = 300
    ) -> List[Dict[str, Any]]:
        """分页获取全部数据。"""
        all_items: List[Dict[str, Any]] = []
        page = 1
        while len(all_items) < max_items:
            p = dict(params or {})
            p["per_page"] = min(100, max_items - len(all_items))
            p["page"] = page
            page_items = self._get(url, params=p)
            if not isinstance(page_items, list) or not page_items:
                break
            all_items.extend(page_items)
            page += 1
            if len(page_items) < p["per_page"]:
                break
        return all_items


class GitHubAPI(BaseGitHubSession):
    """GitHub REST API 封装。"""

    # ── 公开接口 ──────────────────────────────────────────

    def get_repos(self, owner: str, max_items: int = 300) -> List[Dict[str, Any]]:
        """获取用户/组织的所有公开仓库。"""
        items = self._get_paginated(
            f"{API_BASE}/users/{owner}/repos",
            params={"sort": "updated", "direction": "desc"},
            max_items=max_items,
        )
        if not items:
            items = self._get_paginated(
                f"{API_BASE}/orgs/{owner}/repos",
                params={"sort": "updated", "direction": "desc"},
                max_items=max_items,
            )
        return items

    def get_repo_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """获取仓库的语言分布。"""
        return self._get(f"{API_BASE}/repos/{owner}/{repo}/languages")

    def search_repos(self, query: str, max_items: int = 100) -> List[Dict[str, Any]]:
        """搜索仓库。"""
        params = {"q": query, "sort": "stars", "order": "desc"}
        return self._get_paginated(
            f"{API_BASE}/search/repositories",
            params=params,
            max_items=max_items,
        )

    def get_user_info(self, username: str) -> Dict[str, Any]:
        """获取 GitHub 用户基本信息。"""
        return self._get(f"{API_BASE}/users/{username}")

    def collect_repo_data(self, owner: str, max_repos: int = 200) -> List[Dict[str, Any]]:
        """采集完整的仓库数据（基础信息 + 语言统计）。"""
        repos = self.get_repos(owner, max_items=max_repos)
        if not repos:
            return []

        total = len(repos)
        print(f"  共发现 {total} 个仓库")

        formatted: List[Dict[str, Any]] = []
        for i, repo in enumerate(repos):
            if (i + 1) % 20 == 0 or i == 0 or i == total - 1:
                print(f"    处理中... {i + 1}/{total}")

            lic = repo.get("license") or {}
            formatted.append({
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": (repo.get("description") or "")[:200],
                "html_url": repo["html_url"],
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "watchers": repo.get("watchers_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "language": repo.get("language") or "Other",
                "topics": ",".join(repo.get("topics", [])),
                "size_kb": repo.get("size", 0),
                "license_name": lic.get("spdx_id", lic.get("name", "None")),
                "created_at": repo.get("created_at", ""),
                "updated_at": repo.get("updated_at", ""),
                "pushed_at": repo.get("pushed_at", ""),
                "is_fork": repo.get("fork", False),
                "archived": repo.get("archived", False),
            })

        return formatted
