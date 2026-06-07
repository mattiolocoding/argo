# PRODUCT.md — ARGO

> Context file for design work (read by the `impeccable` skill). Describes what
> ARGO is, who uses it, and the design intent of its interface.

## What it is

ARGO is a **local-first AI companion for Windows**. It runs entirely on the user's
machine (Ollama for reasoning), watches files and system events, remembers across
sessions, and acts on the user's files under explicit, governed permission. It is
not a cloud chatbot: it is a persistent "digital being" that lives on the PC.

**Register:** product / dashboard (the design SERVES the tool; it is not a marketing site).

## Who uses it

A single technical-but-pragmatic owner ("Davide") on their personal Windows PC.
They keep the app window open or in the tray during the day. They want to glance at
what ARGO is doing, approve or reject proposed actions, chat with it, and inspect
the audit/console when they care to. Trust, privacy, and "no surprises" matter more
than flashiness.

## The interface

A single self-contained `ui/index.html`, served by the local engine on
`127.0.0.1:8773`. Often shown in a narrow native desktop window (~540px wide), so
**narrow-width robustness is a first-class requirement**, not an afterthought.

Four views, reached from a left icon sidebar:

- **Chat** — conversation with ARGO, plus a live activity bar and action proposals
  shown as approve/reject cards.
- **Console** — operational dashboard: status, memory, governance (role, policy,
  audit integrity), specialized agents, metrics, cognitive system.
- **Permissions** — first-run onboarding and ongoing control of what ARGO may watch
  (Whole PC / Only chosen folders / Nothing).
- **Audit** — the tamper-evident, hash-chained action log.

## Design intent

- **Calm, trustworthy, dark.** A deep navy surface with indigo→violet brand accents
  (matching the logo). The mood is a quiet control room, not a neon dashboard.
- **Glanceable status.** The user should understand ARGO's state (brain online,
  memories, watched folders, current autonomy mode) in under a second.
- **No surprises.** Actions are proposed clearly with plain-language, verb-first
  labels; destructive or sensitive actions are visibly gated.
- **Accessible & legible** at body sizes, with real focus states and reduced-motion
  support. It runs for hours; it must never feel noisy or hard to read.

## Identity to preserve

- Dark theme, deep navy backgrounds.
- Brand gradient indigo `#6366f1` → violet `#8b5cf6` (logo and accents).
- Italian UI language.
- Single-file UI, stdlib engine, zero external web framework.
