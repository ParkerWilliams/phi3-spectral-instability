# QuakeC: rerelease base + FrikBot integration

This directory is our game progs source: the **GPLv2 Quake rerelease QuakeC**
with **FrikBot X v0.10.2** (Public Domain) patched in as the bot. It compiles
to `progs.dat` via fteqcc (`just build-quakec`).

> ⚠️ **Not yet compile-verified.** The droplet has 1 GB RAM and we do not build
> there, so the integration below was applied by inspection. The first **local**
> `just build-quakec` is where it gets finished — expect to resolve the open
> issues at the bottom. This is the vertical-slice handoff point, not a
> known-good build.

## Sources / pins

| Part | Source | Pin | License |
|---|---|---|---|
| Base QuakeC | `id-Software/quake-rerelease-qc`, `quakec/` (id1 base) | `7bcbd29c9934e8523974263de50b3ae90b5d2605` | GPLv2 (`COPYING.txt`) |
| Bot | FrikBot X v0.10.2 (`fbxc.zip`), `Jason2Brownlee/QuakeBotArchive` `bin/fbxc.zip` | release v0.10.2 | Public Domain (notice preserved in every `frikbot/*.qc`) |

`frikbot/bot_qw.qc` (the QuakeWorld variant) is vendored for reference but
**not** in `progs.src` — this is a NetQuake/single-player build.

## What was patched into the rerelease base

Per FrikBot's `src/install.txt`:

- **`progs.src`** — FrikBot's 8 bot files + the 6 `waypoints/map_dm{1..6}.qc`
  inserted immediately after `defs.qc`.
- **`world.qc`** — `BotInit();` at the top of `worldspawn()`; `BotFrame();` at
  the top of `StartFrame()`.
- **`client.qc`** — `if (BotPreFrame()) return;` atop `PlayerPreThink`;
  `if (BotPostFrame()) return;` atop `PlayerPostThink`; `ClientInRankings();`
  atop `ClientConnect`; `ClientDisconnected();` atop `ClientDisconnect`.
- **`defs.qc`** — 14 builtin declarations FrikBot replaces are commented out and
  marked `//FRIKBOT//` (`grep -n //FRIKBOT// defs.qc`): `sound`, `stuffcmd`,
  `sprint`, `aim`, `centerprint`, `setspawnparms`, and `Write{Byte,Char,Short,
  Long,Coord,Angle,String,Entity}`. FrikBot supplies its own versions (which
  call private `frik_*` builtins) in `frikbot/bot.qc`.

The rerelease's own `bots/bot.qc` (a `Bot_PreThink`/`Bot_PostThink` stub whose
AI lives in the closed rerelease engine C++) is left in `progs.src` — it is
inert on FTEQW and harmless.

## Build & run

```bash
just build-fteqcc      # engine/engine/qclib/fteqcc.bin   (LOCAL, not the droplet)
just build-quakec      # quakec/progs.dat
# copy progs.dat into a mod dir beside libre Quake data, launch FTEQW, then:
#   impulse 100   -> add a bot   (101 menus, 102 remove, 103 botcam)
```
FrikBot ships waypoints for `dm1`–`dm6`; start with `dm3`.

## Open issues to resolve at first local compile

1. **`sprint` / `centerprint` mismatch (most likely first break).** The
   rerelease declares these as **extension builtins with varargs + localization
   placeholders** (`sprint = #0:ex_sprint`, and call sites pass `$qc_*`
   localized strings). FrikBot replaces them with **classic single-string**
   versions backed by `frik_sprint = #24` / `frik_centerprint = #73`. Rerelease
   call sites that pass extra/localized args will fail to typecheck or lose
   localization. Resolution options: (a) adapt FrikBot's `sprint`/`centerprint`
   to the rerelease varargs signature and forward to the `ex_` builtins for
   humans, or (b) keep FrikBot's classic versions and fix up the handful of
   rerelease call sites. Decide and document.
2. **Other overridden builtins use classic numbers** (`sound #8`, `stuffcmd
   #21`, `Write* #52–59`, `setspawnparms #78`, `aim #44`). These are standard
   NetQuake builtins that FTEQW implements, so they should be fine — but verify
   the progs loads and bots receive sane network/sound messages.
3. **Rerelease `ex_*` extension builtins elsewhere.** Confirm FTEQW resolves the
   other `#0:ex_name` builtins the rerelease base uses (string localization,
   etc.) or the progs may not load. If not, we may need engine cvars/extensions
   or to strip the localization layer.
4. **`progs.dat` size / field count.** Rerelease + FrikBot is large; if fteqcc
   hits limits, bump with `#pragma` or compiler flags.

When these are settled and it builds+runs, update this file (drop the warning)
and resolve the FrikBot/base entries in `docs/licenses.md`.
