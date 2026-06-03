# Waypointing a LibreQuake map for the agent

FrikBot ships waypoints only for id1 `dm1`–`dm6`. On LibreQuake maps the agent
has no nav graph, so it wanders near spawn, never reaches monsters, and fires
zero shots — which blocks the SC-004 proof (`bot_accuracy` → `stats.accuracy`)
and makes headless runs uninteresting. This is how to author a `.way` file for a
map (starting with `lq_e1m1`) using FrikBot's built-in editor.

> This is **hands-on, run-the-game work on your local machine** (needs the GL
> client + a display). It cannot be done on the droplet. On Windows use WSL2 with
> **WSLg** (Windows 11, or Win10 + recent updates) so the GL window can open.

> 🗄️ **LEGACY / manual fallback — superseded by feature 002.** Automatic
> navigation now generates and persists a `maps/<map>.way` on its own (frontier
> exploration + auto-save in QuakeC; **ADR-0003**, `specs/002-auto-navigation/`).
> Hand-recording is **no longer the path** — it was a bootstrap to unblock
> combat/telemetry on a fixed test map, and procedural maps can't be hand-waypointed
> anyway (`docs/design.md` §3 "Navigation & traversal"). Keep this only as a manual
> fallback for debugging a specific map; normal play depends on the automatic
> process (FR-008), not on anything authored here.

## How loading works

At level start the gamecode runs `exec maps/<map>.way` (that's the
`couldn't exec maps/lq_e1m1.way` line you've seen). A `.way` file is just a
console script that recreates the waypoint graph. Put it in the game dir
(`quakec/maps/`) and **both** the GL client and the headless sim load it.

## 1. Build the GL client (one-time)

The dedicated server skips audio, but the GL client needs the sound dev libs
that aren't installed yet:

```bash
sudo apt install -y libopus-dev libopusfile-dev libvorbis-dev libogg-dev \
                    libspeex-dev libspeexdsp-dev
cd ~/idledoom && just build-engine          # -> engine/engine/release/fteqw-gl
```

## 2. Launch the map (same basedir/game as the sim)

`-nohome` makes the engine read/write under the repo instead of a per-user dir,
so the `.way` you save lands where the sim will find it.

```bash
cd ~/idledoom
engine/engine/release/fteqw-gl -nohome -basedir . -game quakec \
  +set pr_checkextension 1 +map lq_e1m1
```

`pr_checkextension 1` enables FRIK_FILE so the editor can write the `.way`.

## 3. Record waypoints (breadcrumb method)

The stock FrikBot menu editor (`impulse 104`) is fiddly — its on-screen menu
overlays the view and the impulses are menu-context-sensitive. So idledoom adds
two **dedicated, menu-free** impulses (see `frikbot/bot.qc` `BotImpulses`):

- **`impulse 106`** — drop a waypoint at your feet, auto-linked both ways to the
  previous drop, shown as a bubble. (Rebuild progs after pulling: `just build-quakec`.)
- **`impulse 107`** — save every waypoint to `maps/<map>.way`.

Bind them to keys and record by walking:

```
(open console with `, type:)
bind f "impulse 106"
bind g "impulse 107"
```

Close the console, then **walk the map on foot and tap `F` every second or two**
— at every doorway, junction, and room, and especially along the route to the
monsters. Each tap drops a linked bubble; you're laying a connected trail. Stay
on surfaces the agent can actually walk (don't fly/noclip — ground-reachable
points are what it needs). When you've covered the map, press **`G`** once — the
console prints `waypoints saved.` and writes `maps/lq_e1m1.way`.

That's it — no menus. (The full FrikBot menu editor is still there under
`impulse 104` if you ever need fine link editing; its `[0]` option is selected
with `impulse 10`, not `impulse 0`.)

## 4. Place + verify

Find the saved file and make sure it's at `quakec/maps/lq_e1m1.way`:

```bash
find ~/idledoom -name 'lq_e1m1.way'      # confirm where it landed
mkdir -p ~/idledoom/quakec/maps
# move it into place if the engine wrote it elsewhere
```

Then re-run the sim and confirm the agent now fights:

```bash
cd ~/idledoom/sims
uv run harness.py run --config configs/current.toml --time-limit 60
grep -o '"shots_fired": [0-9]*\|"kills": [0-9]*' results/*/*.summary.json | tail
```

`shots_fired` should now be > 0. With combat happening, the SC-004 check works:

```bash
for a in 0.1 0.9; do for i in 1 2 3; do
  uv run harness.py run --config configs/current.toml --time-limit 60 --bot.bot_accuracy $a >/dev/null
done; done
# average stats.accuracy should rise from the 0.1 runs to the 0.9 runs
```

## 5. Commit it

`quakec/maps/lq_e1m1.way` is authored content (like the `dm1`–`dm6` waypoints),
not a build artifact — commit it. Add a `docs/licenses.md` note if the file is
considered a derived work of the LibreQuake map.

> Tip: waypointing a whole episode is tedious. Start with one map (`lq_e1m1`) to
> unblock SC-004; expand coverage as more maps enter the rotation.
