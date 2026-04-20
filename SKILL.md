---
name: library-catalog
description: Catalog, organise, and discover third-party libraries from GitHub across programming languages. Use whenever the user or a calling agent wants to add a library to a personal catalog ("save this repo", "track this library", "add github.com/X/Y"), search by language/category/use case ("what Python HTTP clients do I have?", "find me a Rust web framework", "what async libraries do we know?"), browse the catalog, refresh metadata, or re-categorise entries. Auto-fetches metadata (name, description, language, topics, stars, license) from GitHub's public API and classifies each entry under a predefined taxonomy of categories and sub-categories based on use case. Trigger even when the user doesn't say "catalog" or "library list" — any request about tracking, saving, or rediscovering GitHub repositories belongs here. Also trigger for agent-driven discovery where another Claude instance asks what libraries exist for a given job.
---

# Library Catalog

A persistent, categorised index of GitHub libraries. The catalog lives in `data/libraries.json`, the taxonomy of categories in `data/taxonomy.json`, and four helper scripts in `scripts/` cover the full lifecycle: fetch metadata → classify → add → search.

## When to reach for which flow

Match the user's request to one of these three flows. Don't invent a fourth.

- **Add a library** — the user names a repo (URL or `owner/repo`) and wants it stored, or says "save this", "track this", "add this to my list". See [Adding a library](#adding-a-library).
- **Discover libraries** — the user (or a calling agent) wants to find matching libraries: "what do I have for X?", "find a Go logging library", "show all Python ML libraries". See [Discovering libraries](#discovering-libraries).
- **Browse / manage** — the user wants to see the taxonomy, get counts, or inspect the catalog shape. See [Browsing the taxonomy](#browsing-the-taxonomy).

If the user asks something that isn't one of these (e.g. "which of these is best?"), answer it directly using catalog data as context — don't force the request into a script call.

## Data layout

```
library-catalog/
├── SKILL.md
├── version.json             ← skill version (semver)
├── data/
│   ├── libraries.json       ← the catalog (schema below)
│   └── taxonomy.json        ← allowed categories and sub-categories
└── scripts/
    ├── fetch_repo_metadata.py   ← GitHub → metadata JSON
    ├── add_library.py           ← validate + append to libraries.json
    ├── search_libraries.py      ← query the catalog
    ├── list_categories.py       ← show the taxonomy
    ├── update_skill.py          ← pull updates from remote
    └── bump_version.py          ← increment the version
```

### Library entry schema

Every entry in `libraries.json` looks like this:

```json
{
  "full_name": "tiangolo/fastapi",
  "name": "fastapi",
  "html_url": "https://github.com/tiangolo/fastapi",
  "language": "Python",
  "description": "FastAPI framework, high performance, easy to learn, fast to code",
  "category": "Web Development",
  "sub_category": "Web Framework",
  "use_cases": [
    "Building high-performance REST APIs",
    "Async HTTP services with auto-generated OpenAPI docs"
  ],
  "topics": ["api", "async", "python", "web"],
  "stars": 82000,
  "license": "MIT",
  "added_date": "2026-04-20",
  "last_refreshed": "2026-04-20"
}
```

`category` and `sub_category` must come from `data/taxonomy.json`. Everything else is descriptive.

## Adding a library

This is a three-step flow: **fetch → classify → commit**. The fetch is mechanical, the classification uses judgement, and the commit is validation + write.

### Step 1: Fetch metadata from GitHub

```bash
python3 scripts/fetch_repo_metadata.py <url-or-slug> --pretty
```

Accepted inputs include `https://github.com/owner/repo`, `git@github.com:owner/repo.git`, and the bare slug `owner/repo`. The script prints a JSON object with `name`, `full_name`, `description`, `language`, `topics`, `stars`, `license`, `html_url`, and a `readme_excerpt` (first ~2500 chars of the README).

**If the fetch fails** (network restrictions, 403 from GitHub, archived repo, rate limit): compose the entry by hand using whatever information the user gave you plus what you can see in the repo's web page via your own fetch tool. All fields in the schema above are within reach without the API — the API just makes it faster. Don't abandon the workflow; downgrade to hand-assembly.

Set `GITHUB_TOKEN` in the environment to raise the rate limit from 60 req/hour to 5,000 — useful if ingesting many repos in a session.

### Step 2: Classify

This step is where judgement enters. Take the fetched metadata and decide:

1. **Category and sub-category.** Read `data/taxonomy.json` (or run `python3 scripts/list_categories.py`) and pick the ONE pair that best describes what this library is *for* — not what language it's written in, not what it uses under the hood. If genuinely nothing fits, use `Other → Uncategorized` rather than distorting the taxonomy.
2. **Use cases.** Write 1–5 short phrases (roughly 3–12 words each) describing concrete problems this library solves. Pull these from the README excerpt and the description. Use cases are the primary signal for discovery queries later, so make them specific: "caching API responses in Redis" beats "caching things".

Example of good vs bad use cases for `requests`:
- Good: `["Making HTTP requests with sensible defaults", "Authenticated REST API calls"]`
- Bad: `["HTTP stuff", "Python library for web"]`

### Step 3: Commit

Merge the fetched metadata with your classification into one JSON object and pipe it to `add_library.py`:

```bash
python3 scripts/add_library.py <<'EOF'
{
  "full_name": "tiangolo/fastapi",
  "name": "fastapi",
  "html_url": "https://github.com/tiangolo/fastapi",
  "language": "Python",
  "description": "FastAPI framework, high performance, easy to learn",
  "category": "Web Development",
  "sub_category": "Web Framework",
  "use_cases": ["Building REST APIs with auto-generated OpenAPI docs"],
  "topics": ["api", "async", "python"],
  "stars": 82000,
  "license": "MIT"
}
EOF
```

The script validates required fields, checks the category/sub-category exists in the taxonomy, rejects duplicates, and stamps `added_date` and `last_refreshed`. On duplicate, it exits non-zero with a clear message — add `--update` to overwrite (preserving the original `added_date`).

Use `--dry-run` to validate without writing. That's useful when presenting a proposed entry to the user for confirmation.

### End-to-end example

```bash
# Fetch, then pretty-print so you can read it
METADATA=$(python3 scripts/fetch_repo_metadata.py tokio-rs/tokio)

# Build the final entry by adding classification. In practice you'd
# inspect $METADATA, pick a category, and compose the JSON. Here's the
# result for tokio:
python3 scripts/add_library.py <<'EOF'
{
  "full_name": "tokio-rs/tokio",
  "name": "tokio",
  "html_url": "https://github.com/tokio-rs/tokio",
  "language": "Rust",
  "description": "A runtime for writing reliable asynchronous applications with Rust",
  "category": "Utilities & General",
  "sub_category": "Concurrency / Async",
  "use_cases": ["Async runtime for Rust services", "Building network servers with async I/O"],
  "topics": ["async", "rust", "runtime"],
  "stars": 27500,
  "license": "MIT"
}
EOF
```

## Discovering libraries

`search_libraries.py` is the primary discovery entry point. All filters combine with AND semantics. Results are sorted by stars (descending) by default.

```bash
# Everything
python3 scripts/search_libraries.py

# By language (case-insensitive, matches primary language only)
python3 scripts/search_libraries.py --language python

# By category and sub-category
python3 scripts/search_libraries.py --category "Web Development" --sub-category "Web Framework"

# Free-text across name, description, use_cases, topics
python3 scripts/search_libraries.py --keyword async

# Combine, sort, limit
python3 scripts/search_libraries.py --language rust --min-stars 1000 --limit 5

# JSON out for programmatic consumption (e.g. another agent)
python3 scripts/search_libraries.py --keyword orm --format json
```

**When a calling agent asks "what libraries are there for X?":**

1. Try a narrow query first (exact category + language if both are obvious): `--category "..." --sub-category "..." --language "..."`.
2. If that returns nothing, broaden: drop the sub-category, or switch to `--keyword` with a term from the user's request.
3. If still nothing, report the empty result honestly and offer to ingest new libraries to fill the gap — don't invent entries that aren't there.

**Keyword search tip.** The keyword is a substring match on a concatenation of name, description, use_cases, topics, category, and sub-category. So `--keyword "rate limit"` will match a library whose use-case says "rate limiting API requests" even if its description doesn't mention rate limits. Lean on well-written use cases for this to work.

## Browsing the taxonomy

```bash
# Text tree of categories + sub-categories
python3 scripts/list_categories.py

# Same, but with counts of libraries in each bucket
python3 scripts/list_categories.py --with-counts

# JSON for machine consumption
python3 scripts/list_categories.py --format json --with-counts
```

Run this whenever you need to pick a category for a new library, or to help the user see where the catalog is sparse and where it's deep.

## Evolving the taxonomy

The taxonomy in `data/taxonomy.json` is not sacred — if the user adds several libraries that all land in `Other → Uncategorized`, that's a signal to propose a new sub-category (or category). Edit `data/taxonomy.json`, then optionally use `add_library.py --update` to re-file existing entries. Do this with confirmation from the user, not unilaterally.

## Design notes for agents using this skill

- **The scripts are small and composable on purpose.** They each do one thing so a calling agent can mix them — fetch with one, classify mentally, commit with another; or skip fetch entirely if the user hands you a complete entry.
- **Validation fails loudly.** `add_library.py` prints each validation error on its own line. Treat any non-zero exit as something to show the user, not to silently retry.
- **Use cases are the product.** Stars and topics come from GitHub; what makes this catalog useful later is the human-curated `use_cases` field. When ingesting, spend your judgement budget there.
- **Deduplication is by `full_name`.** `owner/repo` identifies a library uniquely. Case-insensitive comparison handles the `MyOrg/repo` vs `myorg/repo` ambiguity.
- **The catalog file stays sorted** by `full_name` after every write — this keeps git diffs clean when the skill is re-packaged.

## Updating the skill

The skill tracks its version in `version.json` using semver. To check for and apply updates from the remote GitHub repository:

```bash
# Check if an update is available
python3 scripts/update_skill.py --check

# Apply the update (preserves local libraries.json)
python3 scripts/update_skill.py

# Force update even if versions match
python3 scripts/update_skill.py --force

# Update from a different repo or branch
python3 scripts/update_skill.py --repo owner/repo --branch develop
```

The update script compares the local `version.json` against the remote. If the remote version is newer, it shallow-clones the repo, copies updated files (scripts, taxonomy, SKILL.md, version.json), and **preserves the local `data/libraries.json`** so user-added entries are not lost.

### Bumping the version

Before pushing changes to the remote, bump the version so installed copies can detect the update:

```bash
python3 scripts/bump_version.py            # minor: 0.1.0 → 0.2.0
python3 scripts/bump_version.py --major     # major: 0.1.0 → 1.0.0
python3 scripts/bump_version.py --patch     # patch: 0.1.0 → 0.1.1
python3 scripts/bump_version.py --set 2.0.0 # explicit
```

The typical release workflow is: make changes → `bump_version.py` → commit → push.

## Persistence model

Additions write to `data/libraries.json` inside the skill directory. In installed skills this directory may be read-only; if a write fails with a permissions error, the calling agent should either:
- Re-run with `--catalog <writable-path>` pointing at a user-owned copy, or
- Copy the skill to a writable location, work there, and re-package with `package_skill.py` when done.

For routine use where additions need to persist across sessions, the intended workflow is: add libraries during a session, then re-package the skill so the updated `libraries.json` ships with the next install.
