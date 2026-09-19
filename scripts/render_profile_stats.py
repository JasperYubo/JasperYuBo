"""Render self-hosted GitHub profile statistics as deterministic SVG files."""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
COLORS = ("#70a5fd", "#bf91f3", "#38bdae", "#f4d47c", "#f7768e")


class GitHubAPI:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def get(self, path: str) -> object:
        url = API_ROOT + path
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "jasperyubo-profile-stats",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers=headers), timeout=20) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
            except URLError:
                if attempt == 2:
                    raise
            time.sleep(2**attempt)
        raise RuntimeError("GitHub API request failed")


def collect(username: str, client: GitHubAPI) -> tuple[dict[str, int | str], Counter[str]]:
    encoded = quote(username, safe="")
    user = client.get(f"/users/{encoded}")
    if not isinstance(user, dict):
        raise RuntimeError("Unexpected user response")

    repos: list[dict[str, object]] = []
    for page in range(1, 11):
        batch = client.get(
            f"/users/{encoded}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repositories response")
        repos.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            break

    owned = [repo for repo in repos if not repo.get("fork")]
    languages: Counter[str] = Counter()
    for repo in owned:
        full_name = repo.get("full_name")
        if not isinstance(full_name, str):
            continue
        payload = client.get(f"/repos/{quote(full_name, safe='/')}/languages")
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected languages response")
        for language, size in payload.items():
            if isinstance(language, str) and isinstance(size, int) and size > 0:
                languages[language] += size

    stats: dict[str, int | str] = {
        "username": str(user.get("login") or username),
        "repositories": len(owned),
        "stars": sum(int(repo.get("stargazers_count") or 0) for repo in owned),
        "forks": sum(int(repo.get("forks_count") or 0) for repo in owned),
        "followers": int(user.get("followers") or 0),
    }
    return stats, languages


def svg_shell(title: str, description: str, body: str, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="{height}" viewBox="0 0 520 {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>
  <style>
    .title{{font:700 22px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;fill:#70a5fd}}
    .label{{font:500 13px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;fill:#a9b1d6}}
    .value{{font:700 25px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;fill:#c0caf5}}
    .foot{{font:500 12px -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;fill:#787c99}}
  </style>
  <rect width="519" height="{height - 1}" x="0.5" y="0.5" rx="14" fill="#1a1b27" stroke="#343b58"/>
{body}
</svg>
'''


def render_stats(stats: dict[str, int | str]) -> str:
    values = (
        ("公开仓库", stats["repositories"]),
        ("获得 Star", stats["stars"]),
        ("项目 Fork", stats["forks"]),
        ("关注者", stats["followers"]),
    )
    items = []
    for index, (label, value) in enumerate(values):
        x = 34 + (index % 2) * 245
        y = 82 + (index // 2) * 68
        items.append(
            f'  <text class="label" x="{x}" y="{y}">{escape(label)}</text>\n'
            f'  <text class="value" x="{x}" y="{y + 29}">{int(value):,}</text>'
        )
    username = escape(str(stats["username"]))
    body = (
        '  <text class="title" x="28" y="39">Yu Bo 的 GitHub 数据</text>\n'
        + "\n".join(items)
        + f'\n  <text class="foot" x="28" y="194">GitHub @{username} · 仓库自产统计图</text>'
    )
    return svg_shell(
        "Yu Bo 的 GitHub 数据",
        "公开仓库、获得的 Star、项目 Fork 和关注者数量。",
        body,
        210,
    )


def language_rows(languages: Counter[str], limit: int = 5) -> list[tuple[str, int, float]]:
    total = sum(languages.values())
    if total <= 0:
        return []
    return [
        (name, size, size * 100 / total)
        for name, size in languages.most_common(limit)
    ]


def render_languages(languages: Counter[str]) -> str:
    rows = language_rows(languages)
    if not rows:
        body = (
            '  <text class="title" x="28" y="39">常用语言</text>\n'
            '  <text class="label" x="28" y="92">暂无可统计的公开代码。</text>'
        )
        return svg_shell("常用语言", "暂无可统计的公开代码。", body, 150)

    body = ['  <text class="title" x="28" y="39">常用语言</text>']
    for index, (name, _size, percent) in enumerate(rows):
        y = 73 + index * 31
        width = max(2.0, 330 * percent / 100)
        color = COLORS[index % len(COLORS)]
        body.extend(
            (
                f'  <text class="label" x="28" y="{y}">{escape(name)}</text>',
                f'  <text class="label" x="492" y="{y}" text-anchor="end">{percent:.1f}%</text>',
                f'  <rect x="132" y="{y - 10}" width="330" height="10" rx="5" fill="#24283b"/>',
                f'  <rect x="132" y="{y - 10}" width="{width:.1f}" height="10" rx="5" fill="{color}"/>',
            )
        )
    height = 88 + len(rows) * 31
    body.append(
        f'  <text class="foot" x="28" y="{height - 16}">按公开、非 Fork 仓库的代码字节统计</text>'
    )
    description = "；".join(f"{name} {percent:.1f}%" for name, _size, percent in rows)
    return svg_shell("常用语言", description, "\n".join(body), height)


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="JasperYubo")
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    options = parser.parse_args()
    client = GitHubAPI(os.environ.get("GITHUB_TOKEN") or None)
    stats, languages = collect(options.username, client)
    write_atomic(options.output_dir / "github-stats.svg", render_stats(stats))
    write_atomic(options.output_dir / "top-languages.svg", render_languages(languages))
    print(
        json.dumps(
            {
                "username": stats["username"],
                "repositories": stats["repositories"],
                "languages": len(languages),
                "output": str(options.output_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
