#!/usr/bin/env python3
"""
List the category taxonomy, optionally with counts of libraries per bucket.

Agents read this to pick the right category/sub-category when adding a
library, or to browse what's available when exploring the catalog.

Usage:
  python list_categories.py                 # human-readable tree
  python list_categories.py --format json   # machine-readable taxonomy
  python list_categories.py --with-counts   # include per-bucket library counts
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_CATALOG = SKILL_ROOT / "data" / "libraries.json"
DEFAULT_TAXONOMY = SKILL_ROOT / "data" / "taxonomy.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def count_libraries(catalog_path: Path) -> Counter:
    if not catalog_path.exists():
        return Counter()
    catalog = load_json(catalog_path)
    counts: Counter = Counter()
    for lib in catalog.get("libraries", []):
        key = (lib.get("category", "?"), lib.get("sub_category", "?"))
        counts[key] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--with-counts", dest="with_counts", action="store_true",
                        help="Show how many libraries sit in each sub-category.")
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    args = parser.parse_args()

    taxonomy = load_json(Path(args.taxonomy))
    categories = taxonomy.get("categories", {})
    counts = count_libraries(Path(args.catalog)) if args.with_counts else Counter()

    if args.format == "json":
        if args.with_counts:
            out = {
                cat: {sub: counts.get((cat, sub), 0) for sub in subs}
                for cat, subs in categories.items()
            }
        else:
            out = categories
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Text tree
    for cat, subs in categories.items():
        cat_total = sum(counts.get((cat, sub), 0) for sub in subs) if args.with_counts else None
        header = f"{cat}" + (f"  ({cat_total})" if cat_total is not None else "")
        print(header)
        for sub in subs:
            if args.with_counts:
                n = counts.get((cat, sub), 0)
                print(f"  - {sub}  ({n})")
            else:
                print(f"  - {sub}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
