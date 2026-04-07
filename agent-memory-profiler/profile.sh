#!/usr/bin/env bash
set -euo pipefail

#
# Datadog Security Memory Profiler
#
# Measures memory impact of Datadog Security features on both the agent
# (CWS, CSPM, VM/SBOM) and application tracers (AAP, IAST, SCA).
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/configs"
RESULTS_DIR="$SCRIPT_DIR/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CSV_FILE="$RESULTS_DIR/profile_$TIMESTAMP.csv"
SUMMARY_FILE="$RESULTS_DIR/summary_$TIMESTAMP.txt"

AGENT_CONTAINER="secprofiler-agent"
SAMPLE_INTERVAL=10
DEFAULT_DURATION=180
STABILIZE_WAIT=30

SINGLE_FEATURE=""
DURATION=$DEFAULT_DURATION
CATEGORY="all"  # all, agent, tracer
TRACER_LANG=""   # python, node, java, php, or empty for all
MONITOR_ONLY=false
EXTERNAL_CONTAINER=""

AGENT_FEATURES=(
  "cws|Workload Protection (CWS)"
  "sbom_host|VM: Host SBOM"
  "sbom_containers|VM: Container Image SBOM"
  "cspm|CSPM: Compliance Benchmarks"
)

TRACER_FEATURES=(
  "aap|AAP (App & API Protection)|DD_APPSEC_ENABLED"
  "iast|IAST|DD_IAST_ENABLED"
  "sca|SCA Runtime|DD_APPSEC_SCA_ENABLED"
)

ALL_TRACERS=("python" "node" "java" "php")

TRACER_CONTAINERS=(
  ["python"]="secprofiler-python"
  ["node"]="secprofiler-node"
  ["java"]="secprofiler-java"
  ["php"]="secprofiler-php"
)

TRACER_PORTS=(
  ["python"]="8081"
  ["node"]="8082"
  ["java"]="8083"
  ["php"]="8084"
)

# ── Helpers ─────────────────────────────────────────────

usage() {
  cat <<EOF
Datadog Security Memory Profiler

Measures memory impact of Datadog Security features on the agent and tracers.
Produces a summary table + CSV you can attach to JIRA tickets.

Usage: $(basename "$0") [OPTIONS]

Options:
  --feature ID         Test a single feature. Agent: cws, sbom_host, sbom_containers, cspm
                       Tracer: aap, iast, sca
  --category CAT       Which side to test: agent, tracer, or all (default: all)
  --tracer LANG        Tracer language: python, node, java, php (default: all four)
  --duration SECS      Sampling duration per phase (default: $DEFAULT_DURATION)
  --monitor-only       Skip toggling, just monitor an existing container
  --container NAME     Container name/ID for monitor-only mode
  -h, --help           Show this help

Examples:
  $(basename "$0")                                       # Full profile (all features, all languages)
  $(basename "$0") --category agent                      # Agent-side features only
  $(basename "$0") --category tracer --tracer python     # Tracer features on Python only
  $(basename "$0") --feature aap --tracer java           # AAP impact on Java tracer
  $(basename "$0") --feature cws --duration 600          # CWS with 10-min sample window
  $(basename "$0") --monitor-only --container my-agent   # Just watch an existing container
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --feature)    SINGLE_FEATURE="$2"; shift 2 ;;
    --category)   CATEGORY="$2"; shift 2 ;;
    --tracer)     TRACER_LANG="$2"; shift 2 ;;
    --duration)   DURATION="$2"; shift 2 ;;
    --monitor-only) MONITOR_ONLY=true; shift ;;
    --container)  EXTERNAL_CONTAINER="$2"; shift 2 ;;
    -h|--help)    usage ;;
    *)            echo "Unknown option: $1"; usage ;;
  esac
done

if [[ -n "$EXTERNAL_CONTAINER" ]]; then
  AGENT_CONTAINER="$EXTERNAL_CONTAINER"
fi

mkdir -p "$RESULTS_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ── Environment Check ───────────────────────────────────

check_prereqs() {
  command -v docker >/dev/null 2>&1 || die "docker is required"
  docker info >/dev/null 2>&1 || die "docker daemon is not running"

  if [[ "$MONITOR_ONLY" == "false" ]]; then
    if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
      die "No .env file found. Copy .env.example to .env and set your DD_API_KEY"
    fi
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    if [[ -z "${DD_API_KEY:-}" || "$DD_API_KEY" == "your_api_key_here" ]]; then
      die "DD_API_KEY not set. Edit .env and add your API key."
    fi
  fi
}

# ── Memory Sampling ─────────────────────────────────────

get_memory_raw() {
  local container="$1"
  docker stats "$container" --no-stream --format '{{.MemUsage}}' 2>/dev/null \
    | awk -F'/' '{print $1}' | xargs || echo "0MiB"
}

parse_memory_mb() {
  local raw="$1"
  if echo "$raw" | grep -qi "gib"; then
    echo "$raw" | sed 's/[^0-9.]//g' | awk '{printf "%.0f", $1 * 1024}'
  elif echo "$raw" | grep -qi "mib"; then
    echo "$raw" | sed 's/[^0-9.]//g' | awk '{printf "%.0f", $1}'
  elif echo "$raw" | grep -qi "kib"; then
    echo "$raw" | sed 's/[^0-9.]//g' | awk '{printf "%.0f", $1 / 1024}'
  else
    echo "$raw" | sed 's/[^0-9.]//g' | awk '{printf "%.0f", $1}'
  fi
}

sample_phase() {
  local phase_name="$1"
  local duration="$2"
  local container="$3"
  local tracer_lang="${4:-}"
  local samples=$((duration / SAMPLE_INTERVAL))

  log "  Sampling $container: $samples readings over ${duration}s"

  local sum_mb=0
  local count=0

  for i in $(seq 1 "$samples"); do
    local raw
    raw=$(get_memory_raw "$container")
    local mb
    mb=$(parse_memory_mb "$raw")
    local ts
    ts=$(date +%s)

    echo "$ts,$phase_name,$mb,$tracer_lang,$container,$raw" >> "$CSV_FILE"

    sum_mb=$((sum_mb + mb))
    count=$((count + 1))

    if [[ $((i % 6)) -eq 0 || $i -eq "$samples" ]]; then
      local avg=$((sum_mb / count))
      log "  [$i/$samples] current: ${mb}MB | avg: ${avg}MB"
    fi

    sleep "$SAMPLE_INTERVAL"
  done

  echo $((sum_mb / count))
}

# ── Traffic Generation ──────────────────────────────────

TRAFFIC_PID=""

generate_tracer_traffic() {
  local port="$1"
  (
    while true; do
      curl -s -o /dev/null "http://localhost:$port/" 2>/dev/null || true
      curl -s -o /dev/null "http://localhost:$port/search?q=test%27OR%201%3D1" 2>/dev/null || true
      curl -s -o /dev/null -X POST -d "username=admin&password=test" "http://localhost:$port/login" 2>/dev/null || true
      sleep 1
    done
  ) &
  TRAFFIC_PID=$!
}

stop_traffic() {
  if [[ -n "${TRAFFIC_PID:-}" ]]; then
    kill "$TRAFFIC_PID" 2>/dev/null || true
    wait "$TRAFFIC_PID" 2>/dev/null || true
    TRAFFIC_PID=""
  fi
}

# ── Agent Config Generation ─────────────────────────────

generate_agent_config() {
  local feature_id="$1"
  cp "$CONFIGS_DIR/baseline.yaml" "$CONFIGS_DIR/active.yaml"

  if [[ "$feature_id" == "baseline" ]]; then
    return
  fi

  local cfg="$CONFIGS_DIR/active.yaml"

  case "$feature_id" in
    cws)
      python3 -c "
import yaml
with open('$cfg') as f: c = yaml.safe_load(f)
c['runtime_security_config']['enabled'] = True
c['runtime_security_config']['activity_dump']['enabled'] = True
with open('$cfg', 'w') as f: yaml.dump(c, f, default_flow_style=False)
" 2>/dev/null || {
        sed -i.bak '/^runtime_security_config:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        sed -i.bak '/activity_dump:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        rm -f "$cfg.bak"
      }
      ;;
    sbom_host)
      python3 -c "
import yaml
with open('$cfg') as f: c = yaml.safe_load(f)
c['sbom']['enabled'] = True
c['sbom']['host']['enabled'] = True
with open('$cfg', 'w') as f: yaml.dump(c, f, default_flow_style=False)
" 2>/dev/null || {
        sed -i.bak '/^sbom:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        sed -i.bak '/^  host:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        rm -f "$cfg.bak"
      }
      ;;
    sbom_containers)
      python3 -c "
import yaml
with open('$cfg') as f: c = yaml.safe_load(f)
c['sbom']['enabled'] = True
c['sbom']['container_image']['enabled'] = True
with open('$cfg', 'w') as f: yaml.dump(c, f, default_flow_style=False)
" 2>/dev/null || {
        sed -i.bak '/^sbom:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        sed -i.bak '/container_image:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        rm -f "$cfg.bak"
      }
      ;;
    cspm)
      python3 -c "
import yaml
with open('$cfg') as f: c = yaml.safe_load(f)
c['compliance_config']['enabled'] = True
c['compliance_config']['host_benchmarks']['enabled'] = True
with open('$cfg', 'w') as f: yaml.dump(c, f, default_flow_style=False)
" 2>/dev/null || {
        sed -i.bak '/^compliance_config:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        sed -i.bak '/host_benchmarks:/,/enabled:/{s/enabled: false/enabled: true/}' "$cfg"
        rm -f "$cfg.bak"
      }
      ;;
  esac
}

reset_system_probe_config() {
  cat > "$CONFIGS_DIR/system-probe.yaml" <<'YAML'
runtime_security_config:
  enabled: false
  activity_dump:
    enabled: false
YAML
}

# ── Container Lifecycle ─────────────────────────────────

compose() {
  docker compose -f "$SCRIPT_DIR/docker-compose.yml" "$@"
}

start_agent() {
  local feature_id="$1"
  local env_args=""

  case "$feature_id" in
    cws)
      env_args="FEATURE_CWS=true FEATURE_SYSTEM_PROBE=true" ;;
  esac

  if [[ -n "$env_args" ]]; then
    env $env_args compose up -d dd-agent 2>&1 | grep -v "^$" || true
  else
    compose up -d dd-agent 2>&1 | grep -v "^$" || true
  fi
}

stop_all() {
  compose --profile tracer --profile python --profile node --profile java --profile php down 2>&1 | grep -v "^$" || true
}

start_tracer_app() {
  local lang="$1"
  local appsec="${2:-false}"
  local iast="${3:-false}"
  local sca="${4:-false}"

  TRACER_APPSEC="$appsec" TRACER_IAST="$iast" TRACER_SCA="$sca" \
    compose --profile "$lang" up -d "${lang}-app" 2>&1 | grep -v "^$" || true
}

stop_tracer_app() {
  local lang="$1"
  compose --profile "$lang" stop "${lang}-app" 2>&1 | grep -v "^$" || true
  compose --profile "$lang" rm -f "${lang}-app" 2>&1 | grep -v "^$" || true
}

restart_agent() {
  local feature_id="$1"
  log "  Restarting agent with config for: $feature_id"
  reset_system_probe_config

  if [[ "$feature_id" == "cws" ]]; then
    cat > "$CONFIGS_DIR/system-probe.yaml" <<'YAML'
runtime_security_config:
  enabled: true
  activity_dump:
    enabled: true
YAML
  fi

  generate_agent_config "$feature_id"
  compose down dd-agent 2>&1 | grep -v "^$" || true
  start_agent "$feature_id"
  log "  Waiting ${STABILIZE_WAIT}s for agent to stabilize..."
  sleep "$STABILIZE_WAIT"

  if ! docker ps --format '{{.Names}}' | grep -q "$AGENT_CONTAINER"; then
    log "  WARNING: Agent container not running. Checking logs..."
    docker logs "$AGENT_CONTAINER" --tail 20 2>&1 || true
    return 1
  fi
}

# ── Feature Classification ──────────────────────────────

is_agent_feature() {
  local fid="$1"
  for entry in "${AGENT_FEATURES[@]}"; do
    [[ "${entry%%|*}" == "$fid" ]] && return 0
  done
  return 1
}

is_tracer_feature() {
  local fid="$1"
  for entry in "${TRACER_FEATURES[@]}"; do
    [[ "${entry%%|*}" == "$fid" ]] && return 0
  done
  return 1
}

get_tracer_env_var() {
  local fid="$1"
  for entry in "${TRACER_FEATURES[@]}"; do
    local id="${entry%%|*}"
    if [[ "$id" == "$fid" ]]; then
      echo "${entry##*|}"
      return
    fi
  done
}

get_feature_label() {
  local fid="$1"
  for entry in "${AGENT_FEATURES[@]}" "${TRACER_FEATURES[@]}"; do
    local id="${entry%%|*}"
    if [[ "$id" == "$fid" ]]; then
      local rest="${entry#*|}"
      echo "${rest%%|*}"
      return
    fi
  done
  echo "$fid"
}

# ── Monitor-Only Mode ───────────────────────────────────

run_monitor_only() {
  if ! docker ps --format '{{.Names}}' | grep -q "$AGENT_CONTAINER"; then
    die "Container '$AGENT_CONTAINER' not found. Is it running?"
  fi
  log "Monitoring container: $AGENT_CONTAINER for ${DURATION}s"
  echo "timestamp,phase,memory_mb,tracer_language,container,raw" > "$CSV_FILE"
  sample_phase "monitor" "$DURATION" "$AGENT_CONTAINER" ""
  log "Results saved to: $CSV_FILE"
  exit 0
}

# ── Main ────────────────────────────────────────────────

main() {
  check_prereqs

  echo ""
  echo "============================================================"
  echo "  Datadog Security Memory Profiler"
  echo "  $(date)"
  echo "============================================================"
  echo ""

  if [[ "$MONITOR_ONLY" == "true" ]]; then
    run_monitor_only
  fi

  local tracers_to_test=()
  if [[ -n "$TRACER_LANG" ]]; then
    tracers_to_test=("$TRACER_LANG")
  else
    tracers_to_test=("${ALL_TRACERS[@]}")
  fi

  echo "Category           : $CATEGORY"
  echo "Duration per phase : ${DURATION}s"
  echo "Sample interval    : ${SAMPLE_INTERVAL}s"
  if [[ "$CATEGORY" != "agent" ]]; then
    echo "Tracers            : ${tracers_to_test[*]}"
  fi
  echo "Results            : $RESULTS_DIR"
  echo ""

  echo "timestamp,phase,memory_mb,tracer_language,container,raw" > "$CSV_FILE"

  # ---- Determine features to test ----
  local agent_tests=()
  local agent_labels=()
  local tracer_tests=()
  local tracer_labels=()
  local tracer_envvars=()

  if [[ -n "$SINGLE_FEATURE" ]]; then
    if is_agent_feature "$SINGLE_FEATURE"; then
      agent_tests+=("$SINGLE_FEATURE")
      agent_labels+=("$(get_feature_label "$SINGLE_FEATURE")")
    elif is_tracer_feature "$SINGLE_FEATURE"; then
      tracer_tests+=("$SINGLE_FEATURE")
      tracer_labels+=("$(get_feature_label "$SINGLE_FEATURE")")
      tracer_envvars+=("$(get_tracer_env_var "$SINGLE_FEATURE")")
    else
      die "Unknown feature: $SINGLE_FEATURE. Available: cws, sbom_host, sbom_containers, cspm, aap, iast, sca"
    fi
  else
    if [[ "$CATEGORY" == "all" || "$CATEGORY" == "agent" ]]; then
      for entry in "${AGENT_FEATURES[@]}"; do
        agent_tests+=("${entry%%|*}")
        agent_labels+=("${entry#*|}")
      done
    fi
    if [[ "$CATEGORY" == "all" || "$CATEGORY" == "tracer" ]]; then
      for entry in "${TRACER_FEATURES[@]}"; do
        local id="${entry%%|*}"
        local rest="${entry#*|}"
        local label="${rest%%|*}"
        local envvar="${rest##*|}"
        tracer_tests+=("$id")
        tracer_labels+=("$label")
        tracer_envvars+=("$envvar")
      done
    fi
  fi

  declare -A agent_results
  declare -A tracer_results
  local baseline_mb=0

  # ============================================================
  #  AGENT-SIDE PROFILING
  # ============================================================

  if [[ ${#agent_tests[@]} -gt 0 ]]; then
    echo ""
    echo "============================================================"
    echo "  AGENT-SIDE SECURITY FEATURES"
    echo "============================================================"

    # Baseline
    log ""
    log "=== BASELINE (all security features off) ==="
    if ! restart_agent "baseline"; then
      die "Agent failed to start. Check Docker and your .env file."
    fi
    baseline_mb=$(sample_phase "agent_baseline" "$DURATION" "$AGENT_CONTAINER" "")
    log "  Baseline: ${baseline_mb}MB"

    # Per-feature
    for idx in "${!agent_tests[@]}"; do
      local fid="${agent_tests[$idx]}"
      local flabel="${agent_labels[$idx]}"

      log ""
      log "=== $flabel ($fid) ==="

      if ! restart_agent "$fid"; then
        log "  SKIPPED: Agent failed to start with $fid"
        agent_results[$fid]="SKIP|0|N/A"
        continue
      fi

      local feature_mb
      feature_mb=$(sample_phase "agent_$fid" "$DURATION" "$AGENT_CONTAINER" "")

      local delta=$((feature_mb - baseline_mb))
      local pct
      if [[ "$baseline_mb" -gt 0 ]]; then
        pct=$(awk "BEGIN {printf \"%.1f\", ($delta / $baseline_mb) * 100}")
      else
        pct="N/A"
      fi

      agent_results[$fid]="$feature_mb|$delta|$pct"
      log "  Result: ${feature_mb}MB (delta: +${delta}MB, +${pct}%)"
    done
  fi

  # ============================================================
  #  TRACER-SIDE PROFILING
  # ============================================================

  if [[ ${#tracer_tests[@]} -gt 0 ]]; then
    echo ""
    echo "============================================================"
    echo "  TRACER-SIDE SECURITY FEATURES"
    echo "============================================================"

    # Make sure agent is running with baseline config for tracer tests
    if [[ ${#agent_tests[@]} -eq 0 ]]; then
      log ""
      log "Starting agent with baseline config for tracer tests..."
      restart_agent "baseline" || die "Agent failed to start"
    else
      log ""
      log "Resetting agent to baseline for tracer tests..."
      restart_agent "baseline" || true
    fi

    for lang in "${tracers_to_test[@]}"; do
      local container_name="secprofiler-${lang}"
      local port="${TRACER_PORTS[$lang]}"

      log ""
      log "--- Tracer: $lang ---"

      # Tracer baseline (no security features)
      log ""
      log "=== $lang BASELINE (no security features) ==="
      stop_tracer_app "$lang"
      start_tracer_app "$lang" "false" "false" "false"
      log "  Waiting ${STABILIZE_WAIT}s for app to stabilize..."
      sleep "$STABILIZE_WAIT"

      generate_tracer_traffic "$port"
      local tracer_baseline
      tracer_baseline=$(sample_phase "tracer_baseline" "$DURATION" "$container_name" "$lang")
      stop_traffic
      log "  $lang baseline: ${tracer_baseline}MB"

      # Per-feature on this tracer
      for fidx in "${!tracer_tests[@]}"; do
        local fid="${tracer_tests[$fidx]}"
        local flabel="${tracer_labels[$fidx]}"
        local envvar="${tracer_envvars[$fidx]}"

        log ""
        log "=== $lang + $flabel ==="

        stop_tracer_app "$lang"

        local appsec="false" iast="false" sca="false"
        case "$fid" in
          aap) appsec="true" ;;
          iast) iast="true" ;;
          sca) sca="true" ;;
        esac

        start_tracer_app "$lang" "$appsec" "$iast" "$sca"
        log "  Waiting ${STABILIZE_WAIT}s for app to stabilize..."
        sleep "$STABILIZE_WAIT"

        generate_tracer_traffic "$port"
        local feature_mb
        feature_mb=$(sample_phase "tracer_${lang}_${fid}" "$DURATION" "$container_name" "$lang")
        stop_traffic

        local delta=$((feature_mb - tracer_baseline))
        local pct
        if [[ "$tracer_baseline" -gt 0 ]]; then
          pct=$(awk "BEGIN {printf \"%.1f\", ($delta / $tracer_baseline) * 100}")
        else
          pct="N/A"
        fi

        tracer_results["${lang}_${fid}"]="$tracer_baseline|$feature_mb|$delta|$pct"
        log "  Result: ${feature_mb}MB (delta: +${delta}MB, +${pct}%)"
      done

      stop_tracer_app "$lang"
    done
  fi

  # ── Cleanup ───────────────────────────────────────────

  log ""
  log "Cleaning up..."
  stop_all

  # ── Summary ───────────────────────────────────────────

  local summary=""
  summary+="
============================================================
  Datadog Security Memory Profile Summary
  $(date)
  Duration per phase: ${DURATION}s
============================================================
"

  if [[ ${#agent_tests[@]} -gt 0 ]]; then
    summary+="
--- Agent-side Security Features ---
"
    summary+="$(printf "%-40s | %-12s | %-16s | %-9s | %-8s\n" \
      "Feature" "Baseline MB" "With Feature MB" "Delta MB" "Growth %")"
    summary+="
$(printf "%-40s-|-%12s-|-%16s-|-%9s-|-%8s\n" \
      "----------------------------------------" "------------" "----------------" "---------" "--------")"

    for idx in "${!agent_tests[@]}"; do
      local fid="${agent_tests[$idx]}"
      local flabel="${agent_labels[$idx]}"
      if [[ -n "${agent_results[$fid]:-}" ]]; then
        IFS='|' read -r fmb delta pct <<< "${agent_results[$fid]}"
        if [[ "$fmb" == "SKIP" ]]; then
          summary+="
$(printf "%-40s | %-12s | %-16s | %-9s | %-8s" "$flabel" "$baseline_mb" "SKIPPED" "-" "-")"
        else
          summary+="
$(printf "%-40s | %-12s | %-16s | +%-8s | +%-7s" "$flabel" "$baseline_mb" "$fmb" "$delta" "${pct}%")"
        fi
      fi
    done
    summary+="
"
  fi

  if [[ ${#tracer_tests[@]} -gt 0 ]]; then
    summary+="
--- Tracer-side Security Features ---
"
    summary+="$(printf "%-40s | %-8s | %-12s | %-16s | %-9s | %-8s\n" \
      "Feature" "Language" "Baseline MB" "With Feature MB" "Delta MB" "Growth %")"
    summary+="
$(printf "%-40s-|-%8s-|-%12s-|-%16s-|-%9s-|-%8s\n" \
      "----------------------------------------" "--------" "------------" "----------------" "---------" "--------")"

    for lang in "${tracers_to_test[@]}"; do
      for fidx in "${!tracer_tests[@]}"; do
        local fid="${tracer_tests[$fidx]}"
        local flabel="${tracer_labels[$fidx]}"
        local key="${lang}_${fid}"
        if [[ -n "${tracer_results[$key]:-}" ]]; then
          IFS='|' read -r tbase fmb delta pct <<< "${tracer_results[$key]}"
          summary+="
$(printf "%-40s | %-8s | %-12s | %-16s | +%-8s | +%-7s" "$flabel" "$lang" "$tbase" "$fmb" "$delta" "${pct}%")"
        fi
      done
    done
    summary+="
"
  fi

  summary+="
CSV data: $CSV_FILE
"

  echo "$summary" | tee "$SUMMARY_FILE"

  echo ""
  log "Done. Results saved to:"
  log "  CSV:     $CSV_FILE"
  log "  Summary: $SUMMARY_FILE"
  log ""
  log "Generate HTML report: python3 scripts/generate-report.py $CSV_FILE"
}

trap 'stop_traffic; log "Interrupted. Cleaning up..."; stop_all 2>/dev/null; exit 1' INT TERM

main
