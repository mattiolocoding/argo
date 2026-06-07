---
name: crt-screen
description: Use when you want to give a UI element the look of an old CRT/TV screen — scanlines, phosphor glow, screen curvature, flicker, chromatic aberration, and occasional signal interference (roll bar / glitch). Pure CSS, no dependencies. Apply it to an avatar, a "little screen", a chat background, a terminal, or any panel that should feel like retro hardware. Includes a mandatory reduced-motion fallback.
version: 1.0.0
user-invocable: true
---

# CRT screen effect

Turns any container into a believable CRT/TV screen: a dark phosphor surface with
**scanlines**, a soft **glow/bloom**, subtle **screen curvature + vignette**,
gentle **flicker**, light **chromatic aberration**, and an occasional **signal
interference** (a rolling tracking bar + brief glitch). Pure CSS, single file, no
libraries.

## How to apply

1. Wrap (or mark) the element that is the "screen". Its real content (image, eye,
   text, canvas) goes **inside**; the effect layers sit on top via `::before`/`::after`.
2. The screen container needs `position: relative` and `overflow: hidden`.
3. Paste the CSS below (rename `.crt` if it collides). Keep the `@media
   (prefers-reduced-motion: reduce)` block — it is **not optional**.
4. Tune the tokens at the top (`--crt-tint`, `--crt-scan`, `--crt-glow`, speeds).
   Match the host brand: for an indigo product use an indigo/teal phosphor tint, not
   the default green, unless green is the intent.

## CSS

```css
.crt {
  /* --- tokens (tune to brand) --- */
  --crt-tint: 99 102 241;        /* phosphor color (rgb triplet) — indigo by default */
  --crt-scan-gap: 3px;           /* distance between scanlines */
  --crt-scan-opacity: .18;       /* scanline strength */
  --crt-flicker: .04;            /* flicker amplitude (0 = off) */
  --crt-roll-speed: 7s;          /* interference roll period */
  --crt-radius: 16px;

  position: relative;
  overflow: hidden;
  border-radius: var(--crt-radius);
  background: radial-gradient(120% 100% at 50% 50%,
      rgb(var(--crt-tint) / .10), transparent 70%), #05070d;
  /* screen curvature + inner vignette + phosphor glow */
  box-shadow:
    inset 0 0 60px rgba(0,0,0,.65),
    inset 0 0 12px rgb(var(--crt-tint) / .25),
    0 0 0 1px rgb(var(--crt-tint) / .20);
  isolation: isolate;
}
/* the real content gets a faint chromatic aberration + bloom */
.crt > * {
  filter: drop-shadow(0.6px 0 0 rgb(255 0 80 / .35))
          drop-shadow(-0.6px 0 0 rgb(0 200 255 / .35));
}
/* scanlines + flicker */
.crt::before {
  content: "";
  position: absolute; inset: 0; z-index: 2; pointer-events: none;
  background: repeating-linear-gradient(
      to bottom,
      rgba(0,0,0,0) 0,
      rgba(0,0,0,0) calc(var(--crt-scan-gap) - 1px),
      rgba(0,0,0,var(--crt-scan-opacity)) calc(var(--crt-scan-gap) - 1px),
      rgba(0,0,0,var(--crt-scan-opacity)) var(--crt-scan-gap));
  animation: crt-flicker .12s steps(2) infinite;
  mix-blend-mode: multiply;
}
/* rolling interference bar (the signal "tracking" sweep) + soft glass highlight */
.crt::after {
  content: "";
  position: absolute; inset: -50% 0; z-index: 3; pointer-events: none;
  background: linear-gradient(
      to bottom,
      transparent 0,
      rgb(var(--crt-tint) / .06) 48%,
      rgb(255 255 255 / .10) 50%,
      rgb(var(--crt-tint) / .06) 52%,
      transparent 100%);
  height: 60%;
  animation: crt-roll var(--crt-roll-speed) linear infinite;
}
@keyframes crt-flicker {
  0%   { opacity: calc(1 - var(--crt-flicker)); }
  100% { opacity: 1; }
}
@keyframes crt-roll {
  0%   { transform: translateY(-80%); opacity: 0; }
  6%   { opacity: 1; }
  18%  { opacity: 1; }
  26%  { opacity: 0; }
  100% { transform: translateY(260%); opacity: 0; }
}
/* occasional glitch: brief horizontal jitter of the content */
.crt > * { animation: crt-glitch 9s steps(1) infinite; }
@keyframes crt-glitch {
  0%, 96%, 100% { transform: translateX(0); }
  96.5%         { transform: translateX(-1px); }
  97%           { transform: translateX(1.5px); }
  97.5%         { transform: translateX(-0.5px); }
}

@media (prefers-reduced-motion: reduce) {
  .crt::before { animation: none; opacity: 1; }
  .crt::after  { display: none; }
  .crt > *     { animation: none; }
}
```

## Notes
- Keep `--crt-flicker` low (≤ .06); strong flicker is fatiguing and reads as a bug, not a CRT.
- For a tiny avatar "screen", reduce `--crt-scan-gap` to 2px so lines stay visible at small size.
- The chromatic aberration on `.crt > *` is deliberately subtle (sub-pixel). Increase the
  offsets to ~1.2px for a louder, more broken signal.
- If the host already has a `prefers-reduced-motion` block, fold these resets into it instead
  of duplicating the media query.
