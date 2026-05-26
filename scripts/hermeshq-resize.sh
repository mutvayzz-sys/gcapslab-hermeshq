#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/hermeshq}"
ENV_FILE=""

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

usage() {
    cat <<'EOF'
Usage: hermeshq-resize [OPTIONS]

Options:
  --agents N     Resize deployment for N agents (validates resources, updates config)
  --detect       Show current deployment stats and system resources
  --help         Show this help message

Examples:
  hermeshq-resize --agents 100
  hermeshq-resize --detect
EOF
}

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        fail "Required command '$1' not found. Please install it and try again."
    fi
}

fail() {
    printf "\n  ❌ %s\n\n" "$1" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# System resource detection
# ---------------------------------------------------------------------------

detect_system_resources() {
    local os_type
    os_type="$(uname -s)"

    if [ "$os_type" = "Linux" ]; then
        local ram_line
        ram_line="$(free -m | awk '/^Mem:/{print $2, $7}')"
        SYS_TOTAL_RAM_MB="$(printf '%s' "$ram_line" | awk '{print $1}')"
        SYS_AVAILABLE_RAM_MB="$(printf '%s' "$ram_line" | awk '{print $2}')"
        SYS_CPU_CORES="$(nproc)"
        SYS_AVAILABLE_DISK_GB="$(df -BG "$INSTALL_DIR" | awk 'NR==2{gsub(/G/,"",$4); print $4}')"
    elif [ "$os_type" = "Darwin" ]; then
        local mem_bytes
        mem_bytes="$(sysctl -n hw.memsize)"
        SYS_TOTAL_RAM_MB=$((mem_bytes / 1024 / 1024))
        SYS_AVAILABLE_RAM_MB=$(( SYS_TOTAL_RAM_MB * 70 / 100 ))
        SYS_CPU_CORES="$(sysctl -n hw.ncpu)"
        SYS_AVAILABLE_DISK_GB="$(df -g "$INSTALL_DIR" | awk 'NR==2{printf "%d", $4}')"
    else
        fail "Unsupported operating system: $os_type"
    fi
}

# ---------------------------------------------------------------------------
# Sizing calculations
# ---------------------------------------------------------------------------

calculate_sizing() {
    local total_agents="$1"

    local concurrent=$((total_agents / 2))
    local semaphore="$concurrent"

    SIZING_CONCURRENT="$concurrent"
    SIZING_SEMAPHORE="$semaphore"
    SIZING_RAM_BACKEND=$((semaphore * 50 + 500))
    SIZING_RAM_POSTGRES=$((semaphore * 10 + 200))
    SIZING_RAM_TOTAL=$((SIZING_RAM_BACKEND + SIZING_RAM_POSTGRES + 256))
    SIZING_CPU=$((semaphore / 6 + 1))
    SIZING_DISK=$((total_agents * 1500 / 1000 + 5))
}

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

format_mb() {
    local value_mb="$1"
    if [ "$value_mb" -ge 1024 ]; then
        local gb=$((value_mb / 1024))
        printf "%d GB" "$gb"
    else
        printf "%d MB" "$value_mb"
    fi
}

# ---------------------------------------------------------------------------
# Read current semaphore from .env
# ---------------------------------------------------------------------------

read_current_semaphore() {
    local env_path="${INSTALL_DIR}/.env"
    if [ -f "$env_path" ]; then
        local val
        val="$(grep -E '^CONCURRENCY_SEMAPHORE=' "$env_path" 2>/dev/null | tail -1 | cut -d'=' -f2 || true)"
        if [ -n "$val" ]; then
            printf '%s' "$val"
            return
        fi
    fi
    printf '8'
}

# ---------------------------------------------------------------------------
# Print a comparison table
# ---------------------------------------------------------------------------

print_comparison_table() {
    local needed_ram="$1"
    local needed_cpu="$2"
    local needed_disk="$3"
    local avail_ram="$4"
    local avail_cpu="$5"
    local avail_disk="$6"
    local semaphore="$7"

    local ram_ok="✅"
    local cpu_ok="✅"
    local disk_ok="✅"

    [ "$needed_ram" -gt "$avail_ram" ] && ram_ok="❌"
    [ "$needed_cpu" -gt "$avail_cpu" ] && cpu_ok="❌"
    [ "$needed_disk" -gt "$avail_disk" ] && disk_ok="❌"

    local needed_ram_fmt avail_ram_fmt
    needed_ram_fmt="$(format_mb "$needed_ram")"
    avail_ram_fmt="$(format_mb "$avail_ram")"
    local avail_disk_fmt="${avail_disk} GB"
    local needed_disk_fmt="${needed_disk} GB"

    printf '    ┌──────────────┬─────────────┬──────────────┐\n'
    printf '    │ %-12s │ %-11s │ %-12s │\n' "Resource" "Needed" "Available"
    printf '    ├──────────────┼─────────────┼──────────────┤\n'
    printf '    │ %-12s │ %-11s │ %-9s %s │\n' "RAM" "$needed_ram_fmt" "$avail_ram_fmt" "$ram_ok"
    printf '    │ %-12s │ %-11s │ %-9s %s │\n' "CPU" "${needed_cpu} cores" "${avail_cpu} cores" "$cpu_ok"
    printf '    │ %-12s │ %-11s │ %-9s %s │\n' "Disk" "$needed_disk_fmt" "$avail_disk_fmt" "$disk_ok"
    printf '    │ %-12s │ %-11s │ %-12s │\n' "Semaphore" "$semaphore" ""
    printf '    └──────────────┴─────────────┴──────────────┘\n'
}

# ---------------------------------------------------------------------------
# PostgreSQL tuning
# ---------------------------------------------------------------------------

calculate_postgres_tuning() {
    local pg_ram_mb="$1"

    PG_SHARED_BUFFERS=$((pg_ram_mb / 4))
    PG_EFFECTIVE_CACHE=$((pg_ram_mb * 3 / 4))
    PG_MAX_CONNECTIONS=$((SIZING_SEMAPHORE * 2))
    if [ "$PG_MAX_CONNECTIONS" -lt 50 ]; then
        PG_MAX_CONNECTIONS=50
    fi
}

# ---------------------------------------------------------------------------
# Generate docker-compose.override.yml
# ---------------------------------------------------------------------------

generate_docker_override() {
    local semaphore="$1"

    # CPU calculation without bc: round to 1 decimal place
    # Formula: semaphore / 6 + 1, rounded to 1 decimal
    local cpu_int=$(( semaphore / 6 + 1 ))
    local cpu_frac=$(( (semaphore % 6) * 10 / 6 ))
    # Round up if remainder >= 3 (out of 6)
    if [ "$(( semaphore % 6 ))" -ge 3 ]; then
        cpu_frac=$(( cpu_frac + 1 ))
        if [ "$cpu_frac" -ge 10 ]; then
            cpu_frac=0
            cpu_int=$(( cpu_int + 1 ))
        fi
    fi
    local cpu_backend="${cpu_int}.${cpu_frac}"
    local cpu_postgres="0.5"

    cat > "${INSTALL_DIR}/docker-compose.override.yml" <<EOF
services:
  postgres:
    command: >
      postgres
        -c shared_buffers=${PG_SHARED_BUFFERS}MB
        -c max_connections=${PG_MAX_CONNECTIONS}
        -c work_mem=64MB
        -c effective_cache_size=${PG_EFFECTIVE_CACHE}MB
    deploy:
      resources:
        limits:
          memory: ${SIZING_RAM_POSTGRES}M
          cpus: '${cpu_postgres}'
  backend:
    deploy:
      resources:
        limits:
          memory: ${SIZING_RAM_BACKEND}M
          cpus: '${cpu_backend}'
  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
EOF

    printf "  ✔ Generated %s/docker-compose.override.yml\n" "$INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# Update .env semaphore value
# ---------------------------------------------------------------------------

update_env_semaphore() {
    local semaphore="$1"
    local env_path="${INSTALL_DIR}/.env"

    if grep -q '^CONCURRENCY_SEMAPHORE=' "$env_path" 2>/dev/null; then
        if [ "$(uname -s)" = "Darwin" ]; then
            sed -i '' "s/^CONCURRENCY_SEMAPHORE=.*/CONCURRENCY_SEMAPHORE=${semaphore}/" "$env_path"
        else
            sed -i "s/^CONCURRENCY_SEMAPHORE=.*/CONCURRENCY_SEMAPHORE=${semaphore}/" "$env_path"
        fi
    else
        printf 'CONCURRENCY_SEMAPHORE=%s\n' "$semaphore" >> "$env_path"
    fi

    printf "  ✔ Updated CONCURRENCY_SEMAPHORE=%s in %s\n" "$semaphore" "$env_path"
}

# ---------------------------------------------------------------------------
# --agents N mode
# ---------------------------------------------------------------------------

do_agents_mode() {
    local agents_count="$1"

    # Validate install directory
    if [ ! -f "${INSTALL_DIR}/docker-compose.yml" ]; then
        fail "No deployment found at ${INSTALL_DIR}/docker-compose.yml. Run the installer first."
    fi

    # Read current semaphore
    local current_semaphore
    current_semaphore="$(read_current_semaphore)"

    # Detect system resources
    detect_system_resources

    # Calculate sizing
    calculate_sizing "$agents_count"

    # Print header
    printf "\n"
    printf "  Current: semaphore %s\n" "$current_semaphore"
    printf "  Target:  %s agents, semaphore %s\n" "$agents_count" "$SIZING_SEMAPHORE"
    printf "\n"

    # Format values for display
    local needed_ram_fmt avail_ram_fmt
    needed_ram_fmt="$(format_mb "$SIZING_RAM_TOTAL")"
    avail_ram_fmt="$(format_mb "$SYS_AVAILABLE_RAM_MB")"

    local ram_ok="✅"
    local cpu_ok="✅"
    local disk_ok="✅"

    [ "$SIZING_RAM_TOTAL" -gt "$SYS_AVAILABLE_RAM_MB" ] && ram_ok="❌"
    [ "$SIZING_CPU" -gt "$SYS_CPU_CORES" ] && cpu_ok="❌"
    [ "$SIZING_DISK" -gt "$SYS_AVAILABLE_DISK_GB" ] && disk_ok="❌"

    printf "  System resources:\n"
    printf "    RAM:  %s GB available → %s needed %s\n" "$((SYS_AVAILABLE_RAM_MB / 1024))" "$needed_ram_fmt" "$ram_ok"
    printf "    CPU:  %s cores → %s needed %s\n" "$SYS_CPU_CORES" "$SIZING_CPU" "$cpu_ok"
    printf "    Disk: %s GB → %s GB needed %s\n" "$SYS_AVAILABLE_DISK_GB" "$SIZING_DISK" "$disk_ok"
    printf "\n"

    # Warnings
    if [ "$ram_ok" = "❌" ] || [ "$cpu_ok" = "❌" ] || [ "$disk_ok" = "❌" ]; then
        printf "  ⚠️  Insufficient resources detected!\n\n"
    fi

    printf "  This will:\n"
    printf "    1. Update CONCURRENCY_SEMAPHORE=%s in .env\n" "$SIZING_SEMAPHORE"
    printf "    2. Regenerate docker-compose.override.yml\n"
    printf "    3. Restart containers\n"
    printf "\n"

    # Confirmation
    printf "  Proceed? [y/N]: "
    local answer=""
    read -r answer

    case "$answer" in
        [yY]|[yY][eE][sS])
            ;;
        *)
            printf "  Aborted.\n\n"
            exit 0
            ;;
    esac

    printf "\n"

    # Apply changes
    update_env_semaphore "$SIZING_SEMAPHORE"
    calculate_postgres_tuning "$SIZING_RAM_POSTGRES"
    generate_docker_override "$SIZING_SEMAPHORE"

    # Restart containers
    printf "  restarting containers...\n"
    (cd "$INSTALL_DIR" && docker compose up -d)

    printf "\n  ✅ Resize complete!\n"
    printf "     Semaphore: %s → %s\n" "$current_semaphore" "$SIZING_SEMAPHORE"
    printf "     Backend RAM: %s\n" "$(format_mb "$SIZING_RAM_BACKEND")"
    printf "     PostgreSQL RAM: %s (shared_buffers=%sMB)\n" "$(format_mb "$SIZING_RAM_POSTGRES")" "$PG_SHARED_BUFFERS"
    printf "\n"
}

# ---------------------------------------------------------------------------
# --detect mode
# ---------------------------------------------------------------------------

do_detect_mode() {
    # Validate install directory
    if [ ! -d "$INSTALL_DIR" ]; then
        fail "No deployment found at ${INSTALL_DIR}. Run the installer first."
    fi

    # Read current semaphore
    local current_semaphore
    current_semaphore="$(read_current_semaphore)"

    # Detect system resources
    detect_system_resources

    # Calculate max agents that fit
    # max_semaphore = (available_ram - 756) / 60
    local overhead=756
    local ram_for_semaphores=$((SYS_AVAILABLE_RAM_MB - overhead))
    local max_semaphore=1
    if [ "$ram_for_semaphores" -gt 0 ]; then
        max_semaphore=$((ram_for_semaphores / 60))
    fi
    [ "$max_semaphore" -lt 1 ] && max_semaphore=1

    local max_agents=$((max_semaphore * 2))

    # Cap at design maximum of 200 agents
    if [ "$max_agents" -gt 200 ]; then
        max_agents=200
        max_semaphore=100
    fi

    local backend_ram=$((max_semaphore * 50 + 500))
    local pg_ram=$((max_semaphore * 10 + 200))
    local shared_buffers=$((pg_ram / 4))

    local total_ram_gb
    total_ram_gb=$((SYS_TOTAL_RAM_MB / 1024))
    local avail_ram_fmt
    avail_ram_fmt="$(format_mb "$SYS_AVAILABLE_RAM_MB")"

    printf "\n"
    printf "  Current deployment:\n"
    printf "    Semaphore: %s\n" "$current_semaphore"
    printf "    Config: %s/.env\n" "$INSTALL_DIR"
    printf "\n"
    printf "  Detected system resources:\n"
    printf "    RAM:  %d GB total / %s available\n" "$total_ram_gb" "$avail_ram_fmt"
    printf "    CPU:  %s cores\n" "$SYS_CPU_CORES"
    printf "    Disk: %s GB available\n" "$SYS_AVAILABLE_DISK_GB"
    printf "\n"
    printf "  Recommended resize:\n"
    printf "    → Semaphore: %s (for %s agents at 50%% concurrency)\n" "$max_semaphore" "$max_agents"
    printf "    → Backend: %s MB RAM\n" "$backend_ram"
    printf "    → PostgreSQL: %s MB RAM, shared_buffers=%sMB\n" "$pg_ram" "$shared_buffers"
    printf "\n"
    printf "  Run \`hermeshq-resize --agents %s\` to apply.\n" "$max_agents"
    printf "\n"
}

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

main() {
    local mode=""
    local agents_count=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --agents)
                if [ $# -lt 2 ]; then
                    fail "--agents requires a number argument"
                fi
                agents_count="$2"
                shift 2
                ;;
            --detect)
                mode="detect"
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                fail "Unknown option: $1"
                ;;
        esac
    done

    if [ -n "$agents_count" ]; then
        mode="agents"
    fi

    case "$mode" in
        agents)
            # Validate agents_count is a number
            case "$agents_count" in
                ''|*[!0-9]*)
                    fail "--agents must be a positive integer (1-200)"
                    ;;
            esac
            if [ "$agents_count" -lt 1 ] || [ "$agents_count" -gt 200 ]; then
                fail "--agents must be between 1 and 200"
            fi
            need_cmd docker
            do_agents_mode "$agents_count"
            ;;
        detect)
            do_detect_mode
            ;;
        *)
            usage
            exit 0
            ;;
    esac
}

main "$@"
