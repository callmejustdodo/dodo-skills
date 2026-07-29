---
name: mac-lag-doctor
description: "Diagnose macOS lag/slowness with evidence instead of guesses. Separates CPU-bound from memory-bound causes, finds stuck processes and duplicated helper/MCP processes, and A/B-tests every suspect before blaming it. Use when the user says 렉 걸려, 느려, 버벅여, 메모리 많이 먹는 것 같아, 맥이 느려졌어, 'mac is laggy/slow', 'what's eating my CPU/memory', or asks to diagnose system performance."
metadata:
  version: 1.1.0
  openclaw:
    category: "system"
---

# Mac Lag Doctor

Evidence-driven macOS performance diagnosis. The user reports "it's laggy" and usually
guesses a cause ("메모리 too much"). **Their guess is a hypothesis, not a finding.**
Measure first, attribute second, act third.

## The one rule that matters

> **Never blame a process you have not A/B-tested.**

The failure mode this skill exists to prevent: you kill two suspects at once, the
number drops, and you report the wrong culprit. Change **one variable**, measure,
restore. `scripts/ab-test.sh` does exactly this.

Corollary: when you did name the wrong culprit, say so plainly and restore what you
wrongly killed. A confidently-wrong diagnosis costs the user a tool they liked.

## Workflow

### 1. Snapshot (always first)

```bash
SKILL_DIR="$(readlink ~/.claude/skills/mac-lag-doctor || echo ~/.claude/skills/mac-lag-doctor)"
bash "$SKILL_DIR/scripts/snapshot.sh"
```

Read the output and decide **which lane** the problem is in. They are different
problems with different fixes, and both can be true at once:

| Signal | Lane |
|---|---|
| `WindowServer` > 80%, a process pinned high for the full uptime | **CPU lane** |
| Free pages < ~200 MB, compressor > 1.5 GB, huge swapout/decompression counts | **Memory lane** |

### 2. CPU lane — hunt the stuck process

`WindowServer` is the display compositor. When it's hot, **everything** feels laggy
(cursor, scroll, window switching). But it is a *victim* as often as a cause — some
other process is spamming it with render requests.

Find candidates by **elapsed time ≈ uptime + sustained CPU**. A process that has been
pinned at 50% since boot is stuck, not busy.

**System agents go stale.** The highest-yield targets are Apple's own long-running
agents — they auto-respawn instantly, so restarting one is cheap and safe. Confirmed
offenders, all caught at `etime == uptime`:

| Agent | Observed | Effect of restart |
|---|---|---|
| `MenuBarAgent` | stuck; `WindowServer` at 115% | **WindowServer 115.6% → 44.2% (+71pp)** |
| `Siri AI` | 52% since boot | its own CPU → 0; WindowServer 134% → 48% |
| `WindowManager` | 50% for 5 days | its own CPU → 0 (but *not* a WindowServer driver) |

Check these **before** third-party apps. Two lessons from those rows:

1. A stuck agent can be guilty of burning its own CPU **without** driving WindowServer
   (`WindowManager`), or guilty of both (`Siri AI`, `MenuBarAgent`). `ab-test.sh` reports
   both verdicts separately — read both.
2. Auto-respawning agents cannot be tested "with vs without". `ab-test.sh` detects the
   respawn and reframes it as **stale-vs-fresh**, which is the correct experiment.

Third-party menu-bar apps (`Ice`, `Stats`, Bartender-likes) are the *obvious* suspects
and tested **innocent** in every case so far — `Stats` 50.4% vs 48.6%, `Ice` 56.2% vs
53.8%. A/B them, but don't lead the user toward them.

```bash
bash "$SKILL_DIR/scripts/ab-test.sh" MenuBarAgent   # measure → restart → measure → verdict
bash "$SKILL_DIR/scripts/ab-test.sh" "Siri AI"
bash "$SKILL_DIR/scripts/ab-test.sh" WindowManager
```

Verdict threshold: a suspect is guilty only if the target drops by **more than ~10
percentage points** and stays down. Anything smaller is noise.

**Never `kill` WindowServer itself** — it force-logs-out the user. Kill the *driver*.

If nothing tests guilty and `WindowServer` is still hot after days of uptime, say so
plainly rather than inventing a culprit — and be precise about the remedy:

> **Logging out does NOT restart `WindowServer`.** It is a boot-time system process that
> survives logout. Verified: after a full logout/login cycle its `etime` still matched
> uptime (started 2 minutes after `kern.boottime`, 5d22h earlier). **Only a reboot
> resets it.** Check with `ps -o lstart= -p $(pgrep -x WindowServer)` against
> `sysctl -n kern.boottime` before promising anything.

Logout is still worth recommending — it does reset per-user agents (`MenuBarAgent`,
`WindowManager`, `Siri AI`), reclaims accumulated app/session memory, and lets macOS
shrink the swap file. Just don't sell it as a WindowServer fix.

### 3. Memory lane — find duplication, not just big numbers

The biggest single process is rarely the story. **Duplication** is.

`snapshot.sh` aggregates by app family and flags repeated helper processes. Look for:

- **The same MCP server running N times** — one copy per Claude Code session *and* one
  per Claude Desktop. 9× `kordoc`, 7× `context7` is a real observed case (~2.3 GB).
- **`npx -y <pkg>` double-spawn** — `npx` leaves an `npm exec` wrapper node process
  (~90 MB) alive *alongside* the actual server (~60 MB). Installing globally and
  pointing `command` at the real binary halves it with zero functional change.
- **Electron apps** — count all helpers, not just the main process.

Distinguish **regrowth from usage** vs a leak: if RSS climbs right after the user opens
Notion/Chrome, that's normal, not a leak. Check process start times before alarming them.

### 4. Claude Code specifics

Claude Code's daemon pre-warms spare processes. Read `~/.claude/daemon.log`:

```
[bg] bg claimed-spare <session-id> (slash)   → host pid=NNNN
```

Before killing any `bg-spare` / `bg-pty-host`, check whether it is **claimed**:

```bash
ls /tmp/cc-daemon-501/*/spare/
```

- `<id>.claim.sock` **present** → unclaimed spare. Safe to kill.
- `<id>.claim.sock` **gone** → claimed = a real session doing real work. **Do not kill
  blind.** Identify it first (below), then ask the user.

Identify what a claimed session is actually doing:

```bash
lsof -p <pid> | grep -E "\.jsonl|/projects/"       # transcript file
ps -o pid=,args= $(pgrep -P <pid>)                 # children; caffeinate = active work
lsof -p <pid> -i -a | grep ESTABLISHED             # live API calls = still running
```

Then read the tail of the matching `~/.claude/projects/*/<session-id>.jsonl` to see the
last action. A session whose last message is an error and which has been idle for 15+
minutes is **stalled** — it holds hundreds of MB for nothing and is safe to reclaim
(confirm with the user, and fix the underlying cause).

Gotchas:
- **Killing a parent orphans its MCP children.** They reparent to `launchd` and survive.
  Kill the tree, then sweep: `ps -Ao ppid=,pid=,args= | awk '$1==1' | grep mcp`
- **The daemon re-spawns spares.** One-off killing is temporary; reduce spare count if
  it matters.

### 5. Editing MCP config safely

**Never hand-edit `~/.claude.json`** — live sessions rewrite it and will clobber you.
Use the CLI:

```bash
claude mcp remove <name> -s <scope>
```

Scope mapping (verify with `claude mcp list`):

| Scope | File |
|---|---|
| `user` | `~/.claude.json` top-level `mcpServers` |
| `local` | `~/.claude.json` → `projects[<cwd>].mcpServers` |
| `project` | `.mcp.json` in the cwd |

Claude Desktop's config (`~/Library/Application Support/Claude/claude_desktop_config.json`)
has no CLI — edit the JSON directly, but **only while the app is quit**, and preserve
every non-`mcpServers` key (`preferences`, `coworkUserFilesPath`, …).

Back up first, always:

```bash
BK=~/.claude-mcp-backup-$(date +%Y%m%d); mkdir -p "$BK"
cp ~/.claude.json ~/.mcp.json "$BK"/ 2>/dev/null
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json "$BK"/ 2>/dev/null
```

After repointing a server to a global binary, **prove it still works**:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
  | timeout 20 /path/to/binary <args>
```

Config changes only affect **new** sessions — say so; existing sessions keep their
processes.

## Measurement hygiene

These will silently corrupt your numbers:

- **Your own terminal output drives WindowServer.** Redirect sampling to a file and
  print only the summary. Don't measure while streaming output.
- **Discard `top`'s first sample** — it's cumulative-since-boot, not instantaneous.
  Take N+1 samples, drop the first.
- **Check for an active workload first, and re-check between rounds.** A transcription
  pinning `VoiceMemos` at 100%, or Apple's `PhotoAnalysis` / `mediaanalysisd` / Spotlight
  `mdworker` kicking in mid-run, makes every reading after it meaningless. These start on
  their own — a short `etime` next to high CPU is the tell. Note it, or wait it out, and
  never compare a post-workload number to a pre-workload baseline.
- **Report ranges, not single reads.** WindowServer swings ±10pp naturally.

## Shell gotcha (zsh)

The user's shell is zsh, where **unquoted variables do not word-split**. `for p in $PIDS`
iterates once over the whole string. Either use `setopt SH_WORD_SPLIT`, a `while read`
loop, or write the scripts in `#!/usr/bin/env bash` (what `scripts/` does).

## Safety rules

1. Never kill `WindowServer`, `kernel_task`, `launchd`, or `loginwindow`.
2. Never kill a **claimed** background session without identifying it and asking.
3. Quit GUI apps gracefully (`osascript -e 'tell application "X" to quit'`), not `kill -9`.
4. Back up any config before editing.
5. Restore anything you killed that tested innocent.
6. Reach for **log out → log in** to reset per-user agents and reclaim session memory.
   It does **not** touch `WindowServer` — that needs a reboot. Don't conflate the two.

## Reporting

Give the user a before/after table, name the confirmed culprit, and separate
**confirmed** from **unattributed**. If a number didn't fully explain itself, say that
instead of padding the story. End with the concrete remaining options.
