# Design Note: Could Two-Way Zotero Sync Ever Be Done Safely?

Status: exploratory only, per TODO Phase 26. Not a commitment to build this — the current one-way/read-only rule (`AGENTS.md`) stays in force until/unless a future decision explicitly changes it.

## What Ledgerly does today

Two independent, both read-only paths into Zotero:

- **Local library** (`ledgerly/engine/zotero.py`): opens the user's local `zotero.sqlite` via `_connect_readonly` (SQLite opened in explicit read-only mode) to list collections, look up items, and read attachment/full-text caches. Never writes to this file or any other file under the user's Zotero data directory.
- **Zotero Web API** (`ledgerly/engine/zotero_api.py`): only ever issues `GET` requests (`zotero_api_get`) to fetch key info and collections. No `POST`/`PUT`/`PATCH`/`DELETE` calls exist anywhere in the codebase.

This is a deliberate boundary, not an oversight: `AGENTS.md` states "Never modify anything inside the user's local Zotero directory" as a rule that applies to current workflows, dev/test workflows, and any future AI implementation alike.

## Why "two-way sync" is a materially different, higher-risk feature

Writing back to Zotero — e.g. pushing Ledgerly-derived tags, notes, or collection membership into a user's library — is not a bigger version of what exists today; it's a new risk category:

1. **Local SQLite writes are unsafe by design.** Zotero's desktop app holds its own lock on `zotero.sqlite` and expects to be the only writer. A third-party process writing directly to that file while Zotero is running risks corruption or silent data loss that has nothing to do with Ledgerly's own data model. Any write path would have to go through the official Web API, never the local file, full stop — the local SQLite connection would need to stay permanently read-only even if a Web API write path were added.
2. **The Web API write surface has real failure modes**: version-conflict responses (Zotero's API is optimistic-concurrency-controlled via `If-Unmodified-Since-Version`), partial-batch failures, and rate limiting. A naive "just push it" implementation could silently drop updates or overwrite a change the user made in Zotero moments earlier.
3. **It changes the trust model.** Every other Ledgerly feature is additive and reversible: it reads sources, writes its own workspace files, and never touches the user's existing tools' data. A write-back feature means a bug in Ledgerly can now corrupt data in a *different* application the user depends on for their entire reference library — a much larger blast radius than anything else this project does.
4. **Conflict resolution has no obviously correct default.** If a tag or note was edited in both Zotero and Ledgerly since the last sync, "last write wins" silently discards one side's edit — not acceptable given this project's anti-silent-data-loss posture (`AGENTS.md`'s core rules use the same "never silently guess" standard for AI output; the same standard should apply to any sync conflict).

## What would have to be true before this could be built safely

If ever pursued, all of the following would be non-negotiable, not nice-to-haves:

- **Web API only, never local SQLite** — no exception, regardless of how much simpler direct SQLite writes might look.
- **Explicit, granular opt-in** — a user must deliberately enable write-back, per field type (e.g. "sync tags" and "sync notes" as separate toggles), matching this project's existing pattern of narrow, named opt-ins (AI features, per-note-type AI context) rather than one blanket switch.
- **Every write is a proposed diff the user reviews before it's sent**, reusing the same review-before-apply pattern already used for citation-plan insertions and cross-reference candidates — never an automatic background push.
- **Version-checked writes** using Zotero's `If-Unmodified-Since-Version` header, with a hard failure (not a silent overwrite) surfaced to the user on conflict.
- **A local audit log of every write attempt and its outcome**, stored in the Ledgerly workspace, so "what did this tool change in my Zotero library and when" is always answerable.
- **A dry-run mode** that shows exactly what would be sent without sending it, for the user to build trust before ever running it for real.

## Recommendation

Don't build this yet. The read-only boundary is a load-bearing trust guarantee for the project, not an arbitrary limitation, and none of the safety mechanisms above exist today. If a concrete use case emerges that truly needs write-back (as opposed to "would be nice"), scope it as its own phase with its own explicit sign-off — the same way the AI opt-in/cost decision and the multi-tenant decision were each carved out as separate, explicit product decisions rather than folded into existing phases.
