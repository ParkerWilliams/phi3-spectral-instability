# Waypointing a LibreQuake map for the agent

FrikBot ships waypoints only for id1 `dm1`–`dm6`. On LibreQuake maps the agent
has no nav graph, so it wanders near spawn, never reaches monsters, and fires
zero shots — which blocks the SC-004 proof (`bot_accuracy` → `stats.accuracy`)
and makes headless runs uninteresting. This is how to author a `.way` file for a
map (starting with `lq_e1m1`) using FrikBot's built-in editor.

> This is **hands-on, run-the-game work on your local machine** (needs the GL
> client + a display). It cannot be done on the droplet. On Windows use WSL2 with
> **WSLg** (Windows 11, or Win10 + recent updates) so the GL window can open.

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

## 3. Record waypoints

Open the console (`` ` ``) and drive the editor with `impulse` commands (or bind
keys to them). The editor draws each waypoint as a floating bubble.

```
impulse 104     enter the waypoint editor (shows the menu + bubbles)
impulse 5       -> Waylist Management
impulse 5       toggle Dynamic Mode  ON   (auto-drops a waypoint as you move)
impulse 6       toggle Dynamic Link  ON   (auto-links consecutive waypoints)
impulse 7       toggle WAY output    ON   (save format = .way console script)
impulse 0       -> back to Main Menu
```

Now **walk/run through the entire map** — every room and corridor, and
especially toward where the monsters are. Stay on surfaces the agent can reach
(don't noclip through walls; `impulse 6` on the main menu toggles noclip if you
need to cross a gap, but ground-reachable points are what the bot needs). Dynamic
Mode lays down a connected trail behind you.

When the map is covered:

```
impulse 104     re-open the editor menu
impulse 5       -> Waylist Management
impulse 3       Check For Errors   (fix any "links to itself"/orphan warnings)
impulse 4       Save Waypoints     -> writes maps/lq_e1m1.way
```

### Menu reference

```
Main Menu                 Waypoint Mgmt (1)        Waylist Mgmt (5)
 1 Waypoint Management      1 Move Waypoint          1 Delete ALL Waypoints
 2 Link Management          2 Delete Waypoint        2 Dump Waypoints
 3 AI Flag Management       3 Make Waypoint          3 Check For Errors
 4 Bot Management           4 Make Way + Link        4 Save Waypoints
 5 Waylist Management       5 Make Way + Link X2     5 [ ] Dynamic Mode
 6 [ ] Noclip               6 Make Way + Telelink    6 [ ] Dynamic Link
 7 [ ] Godmode              7 Show waypoint info     7 [ ] WAY output
 8 [ ] Hold Select          0 Main Menu              8 [ ] QC output
 9 Teleport to Way #                                 9 [ ] BSP ents output
 0 Close Menu                                        0 Main Menu
```

(Prefer Dynamic Mode for bulk coverage; use Waypoint Mgmt 3/4 to hand-place a
few extra points in tricky spots.)

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
