# ResearchBoss Packaging Plan

This document covers Phase 11: how the CLI, local API, workspace SQLite index, document vault files, and an eventual desktop UI get distributed to a researcher who does not want to set up a Python environment themselves.

Packaging status: planned. Nothing in this document has been built yet — it exists so that when packaging work starts, the approach is already decided rather than improvised.

## What Needs Packaging

- **CLI** (`researchboss` console script, `researchboss.cli:app`) — the primary interface today.
- **Local API** (`researchboss serve`, `researchboss.api`) — FastAPI + uvicorn, needed once a desktop or web UI exists to talk to.
- **Workspace SQLite** — uses Python's stdlib `sqlite3` module; no separate SQLite binary to bundle.
- **Document vault, workspace YAML/Markdown files** — plain files inside a workspace folder; not a packaging concern themselves, but the packaged app must be able to read/write an arbitrary user-chosen folder (no packaging sandbox that blocks that).
- **Web UI** — built (Phase 10): `researchboss/web/`, a Jinja2 + vanilla-JS shell mounted onto the same FastAPI app `researchboss serve` already runs. No separate build step, no separate packaging concern beyond what `[tool.setuptools.package-data]` already handles (bundling `templates/`/`static/` into the wheel) — it ships as part of the existing CLI/API package. Phase 10 did not choose Flutter; the "Future Flutter Desktop Packaging Notes" section below is historical/moot and kept only for context on the option that was considered and passed on.

## Distribution Approaches

Three approaches, not mutually exclusive — a released version could ship more than one:

1. **PyPI package** (`pip install researchboss`) — already the shape `pyproject.toml` produces (`[project.scripts] researchboss = "researchboss.cli:app"`). Zero extra packaging work beyond publishing. Requires the user to have Python 3.11+ installed. Right audience: researchers already comfortable with a terminal and `pip`.
2. **PyInstaller single-file binary** — bundles the interpreter and all dependencies into one executable per platform. No Python install required by the end user. Right audience: everyone else. See below for the concrete recipe and known gotchas.
3. **Docker image** — for `researchboss serve` specifically, not the interactive CLI. Already the target for Phase 12's NAS deployment (`docker-compose.yml`); the same image is not intended for a researcher's personal laptop.

## PyInstaller Notes

Typer/Click console-script entry points don't always resolve cleanly as a PyInstaller target, so use a small wrapper script rather than pointing PyInstaller at the installed `researchboss` script directly:

```python
# packaging/pyinstaller_entry.py
from researchboss.cli import app

if __name__ == "__main__":
    app()
```

```bash
pyinstaller --onefile --name researchboss packaging/pyinstaller_entry.py
```

Known gotchas to verify against, not yet confirmed against a real build:

- **uvicorn's dynamic imports.** uvicorn selects its event loop and HTTP protocol implementations at runtime (`uvicorn.loops.auto`, `uvicorn.protocols.http.auto`, `uvicorn.logging`), which PyInstaller's static import analysis can miss. Expect to need explicit `--hidden-import` flags for these, or a `--collect-all uvicorn` pass, before `researchboss serve` works from the packaged binary even if `researchboss doctor`/`researchboss init` do.
- **`python-multipart`.** Only imported at request-handling time inside FastAPI/Starlette for file uploads (`researchboss api artefacts upload`), so it's an easy one for static analysis to miss entirely. Same treatment as uvicorn above.
- **`sqlite3`.** Bundled with the CPython stdlib; PyInstaller normally includes the `_sqlite3` extension module automatically, but this should be explicitly verified on macOS (where the system Python's SQLite build has caused issues for other projects) rather than assumed.
- **Verify the actual binary, not just that `pyinstaller` exits 0.** Run `researchboss doctor`, `researchboss init` (into a throwaway folder), and `researchboss serve` (hit `/health`) from the packaged executable before calling a platform build done — a clean PyInstaller exit code does not guarantee the runtime imports above actually resolved.

## Future Flutter Desktop Packaging Notes (Moot — Phase 10 Did Not Choose Flutter)

Phase 10 chose a Jinja2 + vanilla-JS web UI (`researchboss/web/`) instead, mounted directly onto the existing FastAPI app — no separate shell process, no sidecar, nothing this section's Flutter-sidecar model would apply to. Left in place as a record of the option that was considered, not as a live plan; do not build against it.

If Flutter is chosen, the local API should run as a sidecar process the Flutter app spawns on launch and stops on exit, rather than embedding a second Python runtime inside the Flutter bundle:

- Reuse the PyInstaller-built `researchboss` binary (above) as a bundled resource inside the Flutter app package, launched via `Process.start` pointed at the bundled binary's path, with `researchboss serve --host 127.0.0.1 --port <ephemeral>`.
- The Flutter app should pick an ephemeral local port and pass it to both the spawned server and its own API client, rather than hard-coding a port that could collide with another local service.
- `RESEARCHBOSS_API_PASSWORD` would need to be generated per-launch (random) and passed to the child process via environment variable, then used internally by the Flutter app's own API client — never surfaced to the end user as something they need to manage, since this is a single local app talking to its own local sidecar, not a shared deployment.
- Avoid a second, independent Python-bundling toolchain (e.g. embedding `briefcase`/`pyapp` inside the Flutter build) purely for this — one packaged binary (PyInstaller's) reused by both the standalone CLI distribution and the Flutter sidecar is less to maintain than two.

## Windows, macOS, and Linux Considerations

### Zotero storage paths

`researchboss.engine.workspace.zotero_storage_candidates()` already covers macOS and Windows default install locations plus their Firefox-style `Profiles/*/storage` variants. Linux was previously unhandled entirely (returned an empty candidate list, so `researchboss init` could never auto-detect a Linux Zotero install) — fixed alongside this packaging plan to check, in order: the native default `~/Zotero/storage`, a native-install profile glob (`~/.zotero/zotero/*/zotero/storage`), and the Flatpak data directory (`~/.var/app/org.zotero.Zotero/data/zotero/storage`). As with the existing macOS/Windows candidates, an unmatched path is simply skipped, not treated as an error — the first candidate that exists on disk wins.

Not yet covered, left as a known gap rather than guessed at: Snap-packaged Zotero on Linux (path conventions vary more by distro/snap-confinement mode than the Flatpak case, and none of this was validated against a real Zotero-on-Linux install — only reasoned about from known Zotero directory conventions).

### Local file permissions

No packaging-specific handling exists yet for restrictive workspace-folder permissions (e.g. a workspace created by one user and later accessed by a packaged binary running as a different user/service account). Not a concern for the CLI's normal single-user local use; would need explicit handling if `researchboss serve` is ever run as a system service rather than a user-launched process — relevant to Phase 12's NAS deployment, not to desktop packaging.

### Document conversion and OCR dependencies

DOCX/PDF conversion (`researchboss.engine.conversion`) is pure-Python/stdlib-adjacent and needs no platform-specific native binary beyond what PyInstaller already bundles for those packages.

OCR is different: `ocr_readiness_report()` locates `tesseract` and `pdftoppm` (poppler-utils) via `shutil.which()` — external system CLI tools, not Python packages. PyInstaller cannot bundle these; a packaged `researchboss` binary will only ever detect a system-installed Tesseract/poppler, never ship one. This needs to be explicit in end-user packaging docs (install Tesseract + poppler separately, per-platform, if OCR fallback is wanted) rather than left implicit — silently falling back to "OCR unavailable" with no explanation would be a worse experience than the CLI already gives (`ocr-readiness` reports exactly which of the two tools is missing).

### SQLite and backups

No known platform-specific packaging concern beyond the `_sqlite3` PyInstaller-bundling verification already noted above. Workspace backups (`researchboss backup`) zip files already inside the user's chosen workspace folder and write the result back into that same folder — no packaging-specific temp-directory or permissions handling needed beyond what the OS already grants the packaged process for that folder.
