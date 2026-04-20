#!/usr/bin/env python3
"""
Search the library catalog.

Agents use this to discover libraries matching a need — by language,
category, sub-category, keyword, or any combination.

Usage:
  # Everything in the catalog
  python search_libraries.py

  # Filter by language (case-insensitive, matches primary language only)
  python search_libraries.py --language python

  # Filter by category and sub-category
  python search_libraries.py --category "Web Development" --sub-category "Web Framework"

  # Free-text keyword search across name, description, use_cases, topics
  python search_libraries.py --keyword "async"

  # Combine filters (AND semantics)
  python search_libraries.py --language rust --category "Web Development"

  # JSON output for agent consumption (default: human-readable text)
  python search_libraries.py --keyword orm --format json

Results are sorted by star count descending by default.
"""

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_CATALOG = SKILL_ROOT / "data" / "libraries.json"


def load_catalog(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("libraries", [])


def matches(lib: dict, filters: argparse.Namespace) -> bool:
    if filters.language:
        lang = (lib.get("language") or "").lower()
        if lang != filters.language.lower():
            return False
    if filters.category:
        if lib.get("category", "") != filters.category:
            return False
    if filters.sub_category:
        if lib.get("sub_category", "") != filters.sub_category:
            return False
    if filters.min_stars is not None:
        if lib.get("stars", 0) < filters.min_stars:
            return False
    if filters.keyword:
        kw = filters.keyword.lower()
        haystack_parts = [
            lib.get("name", ""),
            lib.get("full_name", ""),
            lib.get("description", ""),
            " ".join(lib.get("use_cases", [])),
            " ".join(lib.get("topics", [])),
            lib.get("category", ""),
            lib.get("sub_category", ""),
        ]
        haystack = " ".join(haystack_parts).lower()
        if kw not in haystack:
            return False
    if filters.include_archived is False and lib.get("archived"):
        return False
    return True


def format_text(results: list[dict]) -> str:
    if not results:
        return "No libraries matched."
    lines = [f"{len(results)} librar{'y' if len(results) == 1 else 'ies'} found:\n"]
    for lib in results:
        lines.append(f"• {lib.get('full_name', '?')}  [{lib.get('language') or 'n/a'}]")
        lines.append(
            f"    {lib.get('category', '?')} → {lib.get('sub_category', '?')}"
            f"    ★ {lib.get('stars', 0):,}"
        )
        if lib.get("description"):
            lines.append(f"    {lib['description']}")
        if lib.get("use_cases"):
            lines.append(f"    Use cases: {'; '.join(lib['use_cases'])}")
        lines.append(f"    {lib.get('html_url', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--language", help="Filter by primary language.")
    parser.add_argument("--category", help="Filter by top-level category.")
    parser.add_argument("--sub-category", dest="sub_category", help="Filter by sub-category.")
    parser.add_argument("--keyword", help="Substring search across text fields.")
    parser.add_argument("--min-stars", dest="min_stars", type=int,
                        help="Only return libraries with at least this many stars.")
    parser.add_argument("--include-archived", dest="include_archived",
                        action="store_true",
                        help="Include archived repos in results (excluded by default).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of results to return.")
    parser.add_argument("--sort", choices=["stars", "name", "added_date"], default="stars",
                        help="Sort field. Default: stars (descending).")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format. Default: text.")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG),
                        help=f"Path to the catalog JSON. Default: {DEFAULT_CATALOG}")
    # Default include_archived to False unless the flag is passed
    parser.set_defaults(include_archived=False)
    args = parser.parse_args()

    libraries = load_catalog(Path(args.catalog))
    results = [lib for lib in libraries if matches(lib, args)]

    if args.sort == "stars":
        results.sort(key=lambda lib: lib.get("stars", 0), reverse=True)
    elif args.sort == "name":
        results.sort(key=lambda lib: lib.get("full_name", "").lower())
    elif args.sort == "added_date":
        results.sort(key=lambda lib: lib.get("added_date", ""), reverse=True)

    if args.limit is not None:
        results = results[: args.limit]

    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_text(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
