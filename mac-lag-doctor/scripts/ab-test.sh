#!/usr/bin/env bash
# mac-lag-doctor — A/B test one suspect against a target process.
#
# Quits the suspect, measures the target, relaunches the suspect. ONE variable.
# Sampling is written to a temp file (terminal output itself drives WindowServer).
#
#   ./ab-test.sh "Siri AI"                 # target defaults to WindowServer
#   ./ab-test.sh Stats 12                  # 12-second windows
#   ./ab-test.sh Ice 12 <target-pid>
#
# Exit: 0 = tested, 2 = suspect not running, 3 = target not found.
set -uo pipefail

SUSPECT="${1:?usage: ab-test.sh <app-name-or-process> [seconds] [target-pid]}"
SECS="${2:-12}"
TARGET_PID="${3:-$(pgrep -x WindowServer | head -1)}"

[ -n "$TARGET_PID" ] || { echo "target process not found"; exit 3; }
TARGET_NAME=$(ps -o comm= -p "$TARGET_PID" 2>/dev/null | sed 's|.*/||')
TMP=$(mktemp -t ablag); trap 'rm -f "$TMP"' EXIT

# N+1 samples, drop the first (top's first sample is cumulative-since-boot).
# -n 25 so the suspect itself stays in frame, not just the target.
measure() {
  top -l $((SECS + 1)) -n 25 -s 1 -stats pid,cpu,command > "$TMP" 2>/dev/null
  grep "^$TARGET_PID " "$TMP" | awk '{print $2}' | tail -n "$SECS" | \
    awk '{s+=$1;n++; if(n==1||$1<mn)mn=$1; if($1>mx)mx=$1}
         END{ if(n) printf "%.1f %.1f %.1f %d", s/n, mn, mx, n; else print "0 0 0 0" }'
}

pid_of() { pgrep -x "$SUSPECT" 2>/dev/null | head -1 || pgrep -f "$SUSPECT" 2>/dev/null | head -1; }
cpu_of()  { ps -o pcpu= -p "$1" 2>/dev/null | tr -d ' '; }

SPID=$(pid_of)
[ -n "$SPID" ] || { echo "suspect '$SUSPECT' is not running — nothing to test"; exit 2; }
S_CPU_BEFORE=$(cpu_of "$SPID")

echo "target : $TARGET_NAME (pid $TARGET_PID)"
echo "suspect: $SUSPECT (pid $SPID, lifetime cpu ${S_CPU_BEFORE}%)"
echo "window : ${SECS}s each"
echo

read -r A_AVG A_MIN A_MAX _ <<<"$(measure)"
printf "[A] before  %-16s target avg %5.1f%%   (min %.1f / max %.1f)\n" "" "$A_AVG" "$A_MIN" "$A_MAX"

osascript -e "tell application \"$SUSPECT\" to quit" >/dev/null 2>&1 || kill "$SPID" 2>/dev/null
sleep 3

# Three outcomes, and they mean different things:
#   gone      -> a true without-vs-with comparison
#   new pid   -> macOS auto-respawned it (system agents: WindowManager, Siri AI, ...).
#                That is NOT "without" — it is stale-vs-fresh, which is still the
#                exact test that catches a stuck agent. Label it honestly.
#   same pid  -> quit failed; the run is meaningless.
NPID=$(pid_of)
MODE=gone
if   [ -z "$NPID" ];            then MODE=gone
elif [ "$NPID" = "$SPID" ];     then MODE=failed
else                                 MODE=respawn
fi

case "$MODE" in
  failed) echo "!! could not quit '$SUSPECT' (still pid $SPID) — result unreliable"; ;;
  respawn) echo "note: '$SUSPECT' auto-respawned as pid $NPID — this is a STALE-vs-FRESH test, not with-vs-without"; ;;
esac

read -r B_AVG B_MIN B_MAX _ <<<"$(measure)"
LABEL="without"; [ "$MODE" = respawn ] && LABEL="restarted"
printf "[B] %-9s %-11s target avg %5.1f%%   (min %.1f / max %.1f)\n" "$LABEL" "" "$B_AVG" "$B_MIN" "$B_MAX"

# The suspect's own CPU is a second, independent verdict: an agent stuck at 50%
# for days that drops to ~0 after a restart is a real win even when the target
# never moves. (Observed: Siri AI 52%->0, WindowManager 50%->0.)
if [ "$MODE" = respawn ]; then
  S_CPU_AFTER=$(cpu_of "$NPID")
  printf "    suspect's own cpu: %s%% -> %s%%\n" "$S_CPU_BEFORE" "$S_CPU_AFTER"
fi

echo
DELTA=$(awk -v a="$A_AVG" -v b="$B_AVG" 'BEGIN{printf "%.1f", a-b}')
awk -v d="$DELTA" -v s="$SUSPECT" -v m="$MODE" -v cb="${S_CPU_BEFORE:-0}" -v ca="${S_CPU_AFTER:-0}" 'BEGIN{
  printf "delta  : %+.1f pp (target)\n", d
  if (m == "failed") { print "VERDICT: VOID — suspect never stopped. Re-run."; exit }
  if (d > 10)       printf "VERDICT: GUILTY — %s drives the target.\n", s
  else if (d < -10) printf "VERDICT: NOT the driver — target rose instead. Something else moved.\n"
  else              printf "VERDICT: INNOCENT (target) — within noise.\n"
  if (m == "respawn" && cb-ca > 15)
    printf "         BUT: %s was STUCK (%.1f%% -> %.1f%% after restart). Restarting it is a real win.\n", s, cb, ca
}'

# Restore unless clearly guilty. Auto-respawned agents need nothing.
if [ "$MODE" = gone ] && awk -v d="$DELTA" 'BEGIN{exit !(d<=10)}'; then
  echo
  echo "restoring $SUSPECT ..."
  open -a "$SUSPECT" >/dev/null 2>&1 && echo "  relaunched" || echo "  !! relaunch failed — restore manually"
fi
