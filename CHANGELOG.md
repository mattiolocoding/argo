# Changelog

All notable changes to ARGO are documented here. Format loosely based on
[Keep a Changelog](https://keepachangelog.com/); versioning aims at [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Docker support** for the headless engine: `Dockerfile` (stdlib-only, slim image,
  healthcheck), `docker-compose.yml` (reaches host Ollama via `host.docker.internal`,
  maps `8780:8773`), `.dockerignore`, and `serve.py` (windowless entrypoint). Verified
  live: containerized engine starts healthy, serves the UI, connects to the host LLM.
  Multiple containers form a fleet. The native desktop app remains native.
- Real UI screenshots in the README (chat, console, fleet card).

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
