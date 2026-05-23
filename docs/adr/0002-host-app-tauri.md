# ADR-0002: Use Tauri for the host application

**Status:** Accepted
**Date:** 2026-05-23
**Deciders:** Parker, Taber

## Context

The dual-viewport interface needs a host application that:
- Renders the right-hand upgrade panel (which is half the game's surface and
  requires fast iteration on UI)
- Coordinates with the engine process for stat changes, save state, and
  upgrade application
- Manages save data (SQLite) and player progression state
- Ships as a single distributable per platform
- Has acceptable resource footprint (we don't want a 200MB Electron payload
  for what is essentially a side panel)

The menu UI is where players spend significant attention. We want to iterate
it like a web app — fast feedback, modern styling, easy state management.
The Rust ecosystem also has good library support for process management,
filesystem watching, and SQLite that we'll need for engine coordination.

## Decision

Use **Tauri** (Rust backend + web frontend) for the host application.
Frontend framework to be selected separately; current lean is Svelte or
React (tracked as open question in `docs/design.md`).

## Alternatives considered

- **Native Rust UI (egui / iced)** — single-language stack, smallest
  binaries, no webview dependency. Rejected because UI iteration speed is
  meaningfully slower than web frontends, and the upgrade panel has menu /
  tree / animation needs that web tech handles better out of the box.

- **Electron** — most familiar, broadest library ecosystem. Rejected for
  resource footprint (we're already running an engine process; a 200MB
  Chromium alongside it is wasteful) and because we don't need anything
  Electron offers that Tauri doesn't.

- **In-engine UI (Dear ImGui bindings or QuakeC 2D drawing)** — single
  process, tight integration. Rejected because the right panel is too
  large a surface to iterate inside engine constraints. QuakeC 2D drawing
  is extremely limited; ImGui would work but locks us into immediate-mode
  UI patterns that don't suit menu-heavy interfaces.

- **Separate native window via SDL2 / GLFW** — full control, modest deps.
  Rejected because we'd be reinventing layout, theming, and event handling
  that web frontends give us for free.

- **Tauri (chosen)** — Rust backend gives us solid process management,
  SQLite, filesystem watching. Web frontend gives us fast UI iteration.
  Distributable sizes are modest (~10-20MB typical). v2 has matured.

## Consequences

**Easier:**
- Fast UI iteration in HTML/CSS/JS
- Rust backend cleanly handles engine subprocess management and IPC
- SQLite via `rusqlite` is straightforward
- Cross-platform distribution via Tauri's bundler

**Harder:**
- Window embedding of the engine viewport into the Tauri window is platform-
  specific and finicky. Open question whether we reparent the engine's
  native window or have the engine render to a shared texture/framebuffer
  that Tauri displays. This is a real risk and may force a different
  architecture if neither approach works cleanly.
- Two-language stack (Rust + frontend JS) means context-switching during
  development
- Webview on Linux requires `libwebkit2gtk-4.1-dev`, which adds friction
  to fresh setup (documented in `SETUP.md`)

**Risks and escape hatches:**
- If window embedding proves intractable, fall back to two separate
  top-level windows with coordinated positioning. Less elegant but
  functional.
- If Tauri's resource model conflicts with the engine's window/input
  handling, we can drop to running engine and host as fully independent
  processes communicating only via stdin/file-watching, with the engine
  in its own window.

## References

- Tauri: https://tauri.app/
- Window embedding research: TBD — needs investigation per platform before
  we commit to the reparenting approach
