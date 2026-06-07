# Changelog

All notable changes to ARGO are documented here. Format loosely based on
[Keep a Changelog](https://keepachangelog.com/); versioning aims at [SemVer](https://semver.org/).

## [Unreleased]

### Changed
- **Repo reorganized into a clean tree**: status/planning docs moved to `docs/`, tests to
  `tests/` (with path bootstrap), standalone dev scripts to `scripts/`; removed the dead
  `ponte_sonar.py` (SONAR bridge); README gained a "Project layout" section. CI and
  `.dockerignore` updated to the new paths.
- **UI improved to the impeccable standard**: fixed the chat-view scroll/overflow so the
  feed scrolls cleanly; rebuilt the companion eye with a real eyelid blink (pure CSS);
  removed an AI-tell glow; detector stays at 0.
- **Fixed chat-bubble overlay**: `.live-panel` lacked `overflow:hidden`, so the scrolling
  conversation bubbles bled past the rounded panel and painted over the eye and the cockpit
  cards. Now contained — verified across window sizes.

### Added
- **Roadmap features** (built via a multi-agent workflow, verified live):
  - **Temporal knowledge graph** (`memoria/grafo.py`): edges carry `valido_da`/`valido_a`,
    with an `as-of` neighbor query and a defensive schema migration.
  - **Voice** (`voce.py` + `POST /voce`): real offline TTS via pyttsx3 (ARGO speaks); STT is
    an honest stub. Degrades gracefully without audio.
  - **Update check** (`aggiornamenti.py` + `GET /aggiornamenti`): compares the running version
    against the latest GitHub release; offline-safe.
  - **Central fleet console** (`ui/flotta.html` + `GET /flotta/console`): a standalone page that
    polls `/flotta` and shows aggregated multi-instance status.
  - **PWA / mobile companion** (`ui/manifest.webmanifest`, `ui/sw.js`): installable on a phone,
    with a cache-first shell service worker; engine serves the manifest, SW, and `/assets/`.
  - **Deeper workflow**: a real end-to-end "riordino download" flow with a human approval gate.
  - **Self-signed signing script** (`produzione/build/firma.ps1`): packaging signature via a
    self-signed cert (not CA-trusted — flagged), plus update notes.
- **`crt-screen` skill** (`.claude/skills/crt-screen/`): a reusable, pure-CSS CRT/TV screen
  effect (scanlines, phosphor glow, flicker, chromatic aberration, rolling interference, with
  a reduced-motion fallback). Applied to the companion eye, which now sits on its own little
  CRT screen with signal interference.
- **Docker support** for the headless engine: `Dockerfile` (stdlib-only, slim image,
  healthcheck), `docker-compose.yml` (reaches host Ollama via `host.docker.internal`,
  maps `8780:8773`), `.dockerignore`, and `serve.py` (windowless entrypoint). Verified
  live: containerized engine starts healthy, serves the UI, connects to the host LLM.
  Multiple containers form a fleet. The native desktop app remains native.
- **Fleet demo on Docker** (`docker-compose.fleet.yml`): three ARGO instances on one
  network, one aggregating the others by service name. Verified live: `/flotta`
  reports 3/3 online. New `ARGO_BASE_URL` env so an instance advertises a reachable
  address (avoids the `0.0.0.0` self-base and duplicate entries).
- Real UI screenshots in the README (chat, console, fleet card with the Docker fleet).
- **GHCR publishing** (`.github/workflows/docker.yml`): CI builds and pushes the engine
  image to `ghcr.io/mattiolocoding/argo` on push/tag, with layer caching and semver tags.
- **Self-contained stack** (`docker-compose.ollama.yml`): runs Ollama in a container too,
  so nothing needs to be preinstalled on the host.
- **One-command install**: `install.ps1` (Windows) and `install.sh` (Linux/macOS) one-liners,
  plus a `docker run` one-liner; a new `argo` CLI launcher (`cli.py`) with
  `argo` / `argo engine` / `argo fleet` / `argo version` subcommands.
- README revamped for discoverability: install-in-one-command section, CI/Docker badges, star CTA.

## [0.1.0] — 2026-06-07

First tagged release: the local core runs, is verified live, and the project is
packaged as an open-source repository.

### Added
- **Open-source scaffolding:** README (English), MIT `LICENSE`, `CONTRIBUTING`,
  `SECURITY`, `CODE_OF_CONDUCT`, GitHub Actions CI (compile + module self-tests +
  security suite on Windows), issue/PR templates, `PRODUCT.md`.
- **Horizontal scaling (fleet):** `fleet.py` aggregates multiple ARGO instances in
  parallel via `/identita`; new engine endpoints `/identita` and `/flotta`;
  host/port/instance identity configurable via `ARGO_HOST` / `ARGO_PORT` /
  `ARGO_ISTANZA_ID` / `ARGO_ISTANZA_NOME`. Verified live with two instances.
- **Fleet card** in the Console UI showing aggregated instance status.
- **Unit tests** (`test_fleet.py`): fast, network-free guards for the model-mesh
  embedding exclusion and the fleet aggregation/dedup logic.
- **Deliverable** `COSA_OFFRE_ARGO.md`: full capability catalog + complete API reference.
- Engine version constant (`0.1.0`) surfaced in `/stato` and `/identita`.

### Fixed
- **Model mesh** (`modelli.py`): embedding models (`bge-m3`, `nomic-embed-text`) were
  being assigned to chat roles. They are now excluded; size classification also
  recognizes 14b/13b/20b/27b as large. Roles now resolve to real chat models
  (reflex=qwen2.5:7b, reasoner=llama3.1:8b, expert=qwen2.5:14b).
- **Chat** (`motore_web.py`): `chat()` crashed with `TypeError` because
  `ModelMesh.pensa()` returns a dict and the response was treated as a string
  (a latent bug exposed once the mesh routed to real chat models). The text is now
  extracted with a robust fallback. Verified live: `/chat` returns a grounded answer.

### Changed
- **UI polish to the impeccable standard** (`ui/index.html`): WCAG-compliant contrast,
  typography hierarchy, exponential easing, a mandatory `prefers-reduced-motion` block,
  `:focus-visible` outlines and ARIA roles, and purposeful (non-glow) lighting. The
  anti-pattern detector went from 2 warnings to 0. All JS selectors and API endpoints
  were preserved.

### Security
- Personal/runtime files (`sorvegliata/`, `audit_export.json`, local settings) are
  excluded from version control.

[Unreleased]: https://github.com/mattiolocoding/argo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mattiolocoding/argo/releases/tag/v0.1.0
