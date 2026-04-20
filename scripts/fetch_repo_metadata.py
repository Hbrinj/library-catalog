#!/usr/bin/env python3
"""
Fetch repository metadata from GitHub's public API.

Given a GitHub URL or owner/repo slug, fetch:
  - name, full_name, description, primary language
  - topics, stargazers_count, license
  - canonical html_url
  - an excerpt of the README (first ~2500 chars) for use-case inference

The output is JSON on stdout. This script does NOT classify the library —
that is the calling agent's job. The agent reads this output, examines the
taxonomy, picks a category/sub-category and use cases, then calls
add_library.py with the completed entry.

Usage:
  python fetch_repo_metadata.py https://github.com/tiangolo/fastapi
  python fetch_repo_metadata.py tiangolo/fastapi

Environment variables:
  GITHUB_TOKEN - optional, raises rate limit from 60/hr to 5000/hr
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request


GITHUB_URL_PATTERNS = [
    # https://github.com/owner/repo(.git)?(/...)?
    re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:[/#?].*)?$"),
    # git@github.com:owner/repo.git
    re.compile(r"^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?$"),
    # github.com/owner/repo (no scheme)
    re.compile(r"^github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:[/#?].*)?$"),
    # owner/repo bare slug
    re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9._-]*)$"),
]


def parse_github_url(url: str):
    """Extract (owner, repo) from any common GitHub URL format."""
    url = url.strip()
    for pattern in GITHUB_URL_PATTERNS:
        m = pattern.match(url)
        if m:
            owner, repo = m.group(1), m.group(2)
            # Strip trailing .git if it slipped through
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
    raise ValueError(
        f"Could not parse a GitHub owner/repo from: {url!r}. "
        "Supported formats: https://github.com/owner/repo, "
        "git@github.com:owner/repo.git, or owner/repo."
    )


def _request(url: str, token: str | None = None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "library-catalog-skill")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {e.code} for {url}. "
            f"Body: {body[:300]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e.reason}") from e


def fetch_repo(owner: str, repo: str, token: str | None) -> dict:
    return _request(f"https://api.github.com/repos/{owner}/{repo}", token=token)


def fetch_readme(owner: str, repo: str, token: str | None) -> str:
    try:
        data = _request(
            f"https://api.github.com/repos/{owner}/{repo}/readme", token=token
        )
    except RuntimeError:
        # No README or other issue — not fatal
        return ""
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return content


def readme_excerpt(readme_text: str, max_chars: int = 2500) -> str:
    """Return a trimmed README excerpt suitable for use-case inference.

    Strips HTML comments, collapses whitespace, and caps length. We keep it
    reasonably long so the agent can read the 'what is this / why use it'
    paragraphs that typically appear near the top of a README.
    """
    if not readme_text:
        return ""
    # Strip HTML comments (often badges or metadata)
    text = re.sub(r"<!--.*?-->", "", readme_text, flags=re.DOTALL)
    # Normalize whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return text


def build_metadata(url_or_slug: str, token: str | None = None) -> dict:
    owner, repo = parse_github_url(url_or_slug)
    repo_data = fetch_repo(owner, repo, token)
    readme_text = fetch_readme(owner, repo, token)

    license_info = repo_data.get("license") or {}
    license_id = license_info.get("spdx_id") if isinstance(license_info, dict) else None
    if license_id in (None, "NOASSERTION"):
        license_id = None

    return {
        "owner": owner,
        "repo": repo,
        "name": repo_data.get("name") or repo,
        "full_name": repo_data.get("full_name") or f"{owner}/{repo}",
        "description": (repo_data.get("description") or "").strip(),
        "language": repo_data.get("language"),
        "topics": repo_data.get("topics") or [],
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "open_issues": repo_data.get("open_issues_count", 0),
        "license": license_id,
        "homepage": repo_data.get("homepage") or None,
        "html_url": repo_data.get("html_url") or f"https://github.com/{owner}/{repo}",
        "archived": bool(repo_data.get("archived", False)),
        "pushed_at": repo_data.get("pushed_at"),
        "readme_excerpt": readme_excerpt(readme_text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "target",
        help="GitHub URL or owner/repo slug (e.g. 'tiangolo/fastapi').",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print the JSON output."
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    try:
        meta = build_metadata(args.target, token=token)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.pretty:
        print(json.dumps(meta, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
