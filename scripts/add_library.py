#!/usr/bin/env python3
"""
Add a library entry to the catalog.

The calling agent is expected to have already:
  1. Fetched metadata with fetch_repo_metadata.py
  2. Chosen a category and sub-category from taxonomy.json
  3. Summarised the library's use cases from the README excerpt

This script validates the resulting entry, checks for duplicates, and
appends it to data/libraries.json.

Usage:
  # Pass JSON via stdin:
  echo '{"full_name": "tiangolo/fastapi", ...}' | python add_library.py

  # Or via --json:
  python add_library.py --json '{"full_name": "tiangolo/fastapi", ...}'

  # Update an existing entry:
  python add_library.py --json '...' --update

  # Dry-run (validate only, do not write):
  python add_library.py --json '...' --dry-run

Required fields on the input entry:
  full_name, html_url, name, language, description,
  category, sub_category, use_cases (list of 1-5 short strings)

Optional fields:
  topics, stars, forks, license, homepage, archived, pushed_at, notes
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_CATALOG = SKILL_ROOT / "data" / "libraries.json"
DEFAULT_TAXONOMY = SKILL_ROOT / "data" / "taxonomy.json"

REQUIRED_FIELDS = [
    "full_name",
    "html_url",
    "name",
    "language",
    "description",
    "category",
    "sub_category",
    "use_cases",
]

# Fields we'll copy through if present on the input.
OPTIONAL_FIELDS = [
    "topics",
    "stars",
    "forks",
    "license",
    "homepage",
    "archived",
    "pushed_at",
    "notes",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def validate_entry(entry: dict, taxonomy: dict) -> list[str]:
    """Return a list of validation errors. Empty list means valid."""
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in entry or entry[field] in (None, "", []):
            errors.append(f"Missing required field: {field!r}")

    if "use_cases" in entry and isinstance(entry["use_cases"], list):
        if not (1 <= len(entry["use_cases"]) <= 5):
            errors.append(
                "use_cases must have between 1 and 5 items "
                f"(got {len(entry['use_cases'])})"
            )
        for i, uc in enumerate(entry["use_cases"]):
            if not isinstance(uc, str) or not uc.strip():
                errors.append(f"use_cases[{i}] must be a non-empty string")
    elif "use_cases" in entry:
        errors.append("use_cases must be a list of strings")

    if "/" not in entry.get("full_name", ""):
        errors.append(
            "full_name must be in 'owner/repo' format (e.g. 'tiangolo/fastapi')"
        )

    # Category / sub-category must be in the taxonomy
    categories = taxonomy.get("categories", {})
    category = entry.get("category")
    sub_category = entry.get("sub_category")
    if category and category not in categories:
        valid = ", ".join(sorted(categories.keys()))
        errors.append(
            f"Unknown category {category!r}. Valid categories: {valid}"
        )
    elif category and sub_category:
        valid_subs = categories[category]
        if sub_category not in valid_subs:
            errors.append(
                f"Sub-category {sub_category!r} is not valid under "
                f"{category!r}. Valid sub-categories: {', '.join(valid_subs)}"
            )

    return errors


def normalize_entry(entry: dict) -> dict:
    """Coerce incoming entry into the canonical storage shape."""
    normalized = {
        "full_name": entry["full_name"],
        "name": entry["name"],
        "html_url": entry["html_url"],
        "language": entry.get("language"),
        "description": entry.get("description", "").strip(),
        "category": entry["category"],
        "sub_category": entry["sub_category"],
        "use_cases": [uc.strip() for uc in entry["use_cases"]],
    }
    for field in OPTIONAL_FIELDS:
        if field in entry and entry[field] not in (None, ""):
            normalized[field] = entry[field]
    return normalized


def find_existing(libraries: list, full_name: str) -> int:
    for i, lib in enumerate(libraries):
        if lib.get("full_name", "").lower() == full_name.lower():
            return i
    return -1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--json",
        dest="json_str",
        help="Library entry as a JSON string. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG),
        help=f"Path to the catalog JSON. Default: {DEFAULT_CATALOG}",
    )
    parser.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY),
        help=f"Path to the taxonomy JSON. Default: {DEFAULT_TAXONOMY}",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="If an entry with the same full_name exists, replace it. "
        "Without this flag, duplicates are rejected.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the entry but do not write to the catalog.",
    )
    args = parser.parse_args()

    raw = args.json_str if args.json_str else sys.stdin.read()
    if not raw.strip():
        print("Error: no JSON provided (use --json or pipe to stdin)", file=sys.stderr)
        return 2
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        return 2

    taxonomy = load_json(Path(args.taxonomy))
    errors = validate_entry(entry, taxonomy)
    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    normalized = normalize_entry(entry)
    today = date.today().isoformat()

    catalog_path = Path(args.catalog)
    if catalog_path.exists():
        catalog = load_json(catalog_path)
    else:
        catalog = {"schema_version": "1.0", "libraries": []}

    libraries = catalog.setdefault("libraries", [])
    existing_idx = find_existing(libraries, normalized["full_name"])

    if existing_idx >= 0 and not args.update:
        print(
            f"Error: {normalized['full_name']} is already in the catalog. "
            "Pass --update to replace it.",
            file=sys.stderr,
        )
        return 1

    if existing_idx >= 0:
        # Preserve added_date, refresh last_refreshed
        normalized["added_date"] = libraries[existing_idx].get("added_date", today)
        normalized["last_refreshed"] = today
        libraries[existing_idx] = normalized
        action = "Updated"
    else:
        normalized["added_date"] = today
        normalized["last_refreshed"] = today
        libraries.append(normalized)
        action = "Added"

    # Keep the catalog sorted by full_name for stable diffs
    libraries.sort(key=lambda lib: lib.get("full_name", "").lower())

    if args.dry_run:
        print(f"{action} (dry-run): {normalized['full_name']}")
        print(json.dumps(normalized, indent=2, ensure_ascii=False))
        return 0

    save_json(catalog_path, catalog)
    print(f"{action}: {normalized['full_name']} ({len(libraries)} libraries in catalog)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
