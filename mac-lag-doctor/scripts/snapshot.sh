#!/usr/bin/env bash
# mac-lag-doctor — baseline system snapshot.
# Bash (not zsh) on purpose: we rely on normal word splitting.
#
#   ./snapshot.sh
set -uo pipefail

PAGE=$(vm_stat 2>/dev/null | head -1 | grep -oE '[0-9]+' | head -1); PAGE=${PAGE:-4096}
mb() { awk -v v="$1" -v p="$PAGE" 'BEGIN{printf "%.0f", v*p/1048576}'; }
hr() { printf '\n\033[1m%s\033[0m\n' "$1"; }

hr "1. LOAD / UPTIME"
uptime
NCPU=$(sysctl -n hw.ncpu)
PHYS=$(awk -v m="$(sysctl -n hw.memsize)" 'BEGIN{printf "%.0f", m/1073741824}')
echo "  cores=$NCPU  ram=${PHYS}GB  (load > cores = saturated)"

hr "2. MEMORY PRESSURE"
FREE=$(vm_stat | awk '/Pages free/{gsub(/\./,"");print $NF}')
COMP=$(vm_stat | awk '/occupied by compressor/{gsub(/\./,"");print $NF}')
SWO=$(vm_stat  | awk '/Swapouts/{gsub(/\./,"");print $NF}')
DEC=$(vm_stat  | awk '/Decompressions/{gsub(/\./,"");print $NF}')
printf "  free       : %s MB   %s\n" "$(mb "$FREE")" \
  "$([ "$(mb "$FREE")" -lt 200 ] 2>/dev/null && echo '<-- STARVED' || echo '')"
printf "  compressor : %s MB   %s\n" "$(mb "$COMP")" \
  "$([ "$(mb "$COMP")" -gt 1500 ] 2>/dev/null && echo '<-- heavy compression' || echo '')"
printf "  swapouts   : %s pages (~%s GB since boot)\n" "$SWO" \
  "$(awk -v v="$SWO" -v p="$PAGE" 'BEGIN{printf "%.0f", v*p/1073741824}')"
printf "  decompress : %s pages  (billions = sustained thrashing)\n" "$DEC"
sysctl -n vm.swapusage | sed 's/^/  swap       : /'

hr "3. TOP CPU  (etime ~= uptime + high cpu  =>  STUCK, not busy)"
ps -Ao pcpu=,rss=,pid=,etime=,comm= | sort -rn | head -12 | \
  awk '$1+0>1 {printf "  %6s%%  %7.0f MB  pid=%-7s up=%-12s %s\n",$1,$2/1024,$3,$4,substr($0,index($0,$5))}' | cut -c1-118

hr "4. TOP MEMORY"
ps -Ao rss=,pid=,pcpu=,comm= | sort -rn | head -12 | \
  awk '{printf "  %7.0f MB  pid=%-7s cpu=%-6s %s\n",$1/1024,$2,$3,substr($0,index($0,$4))}' | cut -c1-118

hr "5. DUPLICATED PROCESSES  (the real memory story)"
ps -Ao rss=,args= | awk '
{
  rss=$1; $1="";
  n=split($0,w," "); sig=""; split("",seen)
  # Signature = de-duplicated basenames of the first few non-flag tokens.
  # Path-heavy argv ("/Applications/Google Chrome.app/.../Google Chrome") otherwise
  # yields repeated garbage like "Google Google Chrome Google Chrome".
  for(i=1;i<=n && i<=6;i++){
    t=w[i]; if(t ~ /^-/) continue; sub(/.*\//,"",t)
    if(t=="" || (t in seen)) continue
    seen[t]=1; sig=sig" "t
  }
  if(sig=="") next
  s[sig]+=rss; c[sig]++
}
END{ for(k in s) if(c[k]>=3) printf "  %7.0f MB  x%-3d %s\n", s[k]/1024, c[k], k }' \
  | sort -rn | head -12 | cut -c1-118
echo "  (x3+ of the same server/helper = duplication; npx leaves an extra wrapper per copy)"

hr "6. APP FAMILIES"
# comm= (not args=) — executable path only. Paths contain spaces
# ("/Library/Application Support/..."), so argv splitting would mis-name them.
ps -Ao rss=,comm= | awk '
{ rss=$1; $1=""; p=substr($0,2); app="";
  if (match(p, /\/[^\/]+\.app\//)) { app=substr(p,RSTART+1,RLENGTH-6) }
  else { app=p; sub(/.*\//,"",app) }
  s[app]+=rss; c[app]++ }
END{ for(k in s) if (s[k]/1024 > 150) printf "  %7.0f MB  (%3d procs)  %s\n", s[k]/1024, c[k], k }' \
  | sort -rn | head -12 | cut -c1-118

hr "7. CLAUDE CODE DAEMON / SPARES"
SP=$(ls -d /tmp/cc-daemon-*/*/spare 2>/dev/null | head -1)
if [ -n "$SP" ]; then
  echo "  spare dir: $SP"
  for sock in "$SP"/*.claim.sock; do
    [ -e "$sock" ] || continue
    echo "    UNCLAIMED (safe to kill): $(basename "$sock" .claim.sock)"
  done
  for sock in "$SP"/*.pty.sock; do
    [ -e "$sock" ] || continue
    id=$(basename "$sock" .pty.sock)
    [ -e "$SP/$id.claim.sock" ] || echo "    CLAIMED  (identify before killing): $id"
  done
  ps -Ao rss=,pid=,args= | grep -E 'bg-spare|bg-pty-host' | grep -v grep | \
    awk '{printf "    %6.0f MB pid=%-7s %s\n",$1/1024,$2,$3" "$4}'
else
  echo "  (no daemon spare dir found)"
fi
[ -f ~/.claude/daemon.log ] && { echo "  --- daemon.log tail ---"; tail -4 ~/.claude/daemon.log | cut -c1-110 | sed 's/^/    /'; }

hr "8. TOTALS"
echo "  processes : $(ps -Ao comm= | wc -l | tr -d ' ')"
ps -Ao rss= | awk '{s+=$1} END{printf "  total RSS : %.1f GB\n", s/1024/1024}'
df -h / /System/Volumes/Data 2>/dev/null | tail -n +2 | awk '{printf "  disk      : %s used, %s free (%s)\n",$3,$4,$9}'

hr "NEXT"
cat <<'EOF'
  WindowServer hot?  -> CPU lane.    A/B every suspect:  ./ab-test.sh "<App Name>"
  free < 200MB?      -> Memory lane. Attack duplication (section 5) first.
  Do NOT name a culprit you have not A/B-tested.
EOF
