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
measure() {
  top -l $((SECS + 1)) -n 4 -s 1 -stats pid,cpu,command > "$TMP" 2>/dev/null
  grep "^$TARGET_PID " "$TMP" | awk '{print $2}' | tail -n "$SECS" | \
    awk '{s+=$1;n++; if(n==1||$1<mn)mn=$1; if($1>mx)mx=$1}
         END{ if(n) printf "%.1f %.1f %.1f %d", s/n, mn, mx, n; else print "0 0 0 0" }'
}

pid_of() { pgrep -x "$SUSPECT" 2>/dev/null | head -1 || pgrep -f "$SUSPECT" 2>/dev/null | head -1; }

SPID=$(pid_of)
[ -n "$SPID" ] || { echo "suspect '$SUSPECT' is not running — nothing to test"; exit 2; }

echo "target : $TARGET_NAME (pid $TARGET_PID)"
echo "suspect: $SUSPECT (pid $SPID)"
echo "window : ${SECS}s each"
echo

read -r A_AVG A_MIN A_MAX _ <<<"$(measure)"
printf "[A] with %-18s avg %5.1f%%   (min %.1f / max %.1f)\n" "$SUSPECT" "$A_AVG" "$A_MIN" "$A_MAX"

osascript -e "tell application \"$SUSPECT\" to quit" >/dev/null 2>&1 || kill "$SPID" 2>/dev/null
sleep 3
if pid_of >/dev/null; then echo "!! could not quit '$SUSPECT' — result unreliable"; fi

read -r B_AVG B_MIN B_MAX _ <<<"$(measure)"
printf "[B] without %-15s avg %5.1f%%   (min %.1f / max %.1f)\n" "$SUSPECT" "$B_AVG" "$B_MIN" "$B_MAX"

echo
DELTA=$(awk -v a="$A_AVG" -v b="$B_AVG" 'BEGIN{printf "%.1f", a-b}')
awk -v d="$DELTA" -v s="$SUSPECT" 'BEGIN{
  printf "delta  : %+.1f pp\n", d
  if (d > 10)      printf "VERDICT: GUILTY — %s drives the target. Keep it off.\n", s
  else if (d < -10) printf "VERDICT: inverted — target got WORSE without %s. Re-run; something else moved.\n", s
  else             printf "VERDICT: INNOCENT — within noise. %s is not the cause; restore it.\n", s
}'

# Restore unless clearly guilty: an innocent app must not be left dead.
if awk -v d="$DELTA" 'BEGIN{exit !(d<=10)}'; then
  echo
  echo "restoring $SUSPECT ..."
  open -a "$SUSPECT" >/dev/null 2>&1 && echo "  relaunched" || echo "  !! relaunch failed — restore manually"
fi
