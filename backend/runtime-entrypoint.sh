#!/bin/sh
# Generate the Hermes model config from the provider env injected at provision
# time, then start the Agent37 gateway. The worker reads model settings ONLY from
# $HERMES_HOME/config.yaml (via hermes_cli.config.load_config) — it ignores the
# HERMES_DEFAULT_* env directly — so we materialize them into config.yaml here.
# When no provider is provisioned, the build-time default (baked config.yaml) is
# left in place. The provider's API key (e.g. KIMI_API_KEY) is read from the
# environment by Hermes and does not need to be written into config.yaml.
set -e

CONFIG_DIR="${HERMES_HOME:-/home/hermes/.hermes}"
CONFIG="$CONFIG_DIR/config.yaml"

if [ -n "${HERMES_DEFAULT_PROVIDER:-}" ]; then
  mkdir -p "$CONFIG_DIR"
  {
    echo "model:"
    echo "  provider: ${HERMES_DEFAULT_PROVIDER}"
    [ -n "${HERMES_DEFAULT_MODEL:-}" ] && echo "  default: ${HERMES_DEFAULT_MODEL}"
    [ -n "${HERMES_DEFAULT_BASE_URL:-}" ] && echo "  base_url: \"${HERMES_DEFAULT_BASE_URL}\""
    [ -n "${HERMES_DEFAULT_API_MODE:-}" ] && echo "  api_mode: ${HERMES_DEFAULT_API_MODE}"
    echo "web:"
    echo "  use_gateway: true"
    echo "image_gen:"
    echo "  use_gateway: true"
  } > "$CONFIG"
fi

exec node /opt/agent37-gateway/dist/server/server/index.js
