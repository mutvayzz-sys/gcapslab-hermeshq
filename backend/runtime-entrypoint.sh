#!/bin/sh
# Generate the Hermes model config from the provider env injected at provision
# time, then start the Agent37 gateway. The worker reads model settings ONLY from
# $HERMES_HOME/config.yaml (via hermes_cli.config.load_config) — it ignores the
# HERMES_DEFAULT_* env directly — so we materialize them into config.yaml here.
# When no provider is provisioned, the build-time default (baked config.yaml) is
# left in place. The provider's API key (e.g. KIMI_API_KEY) is read from the
# environment by Hermes and does not need to be written into config.yaml.
#
# $HERMES_HOME now lives on a persistent per-user volume (see
# hermeshq/services/container_supervisor.py::_data_volume_name), so config.yaml
# can carry state written between container restarts — e.g. the gateway's
# /api/mcp/servers route writes an `mcp_servers:` key here. This script MUST
# merge the model/web/image_gen keys into the existing file rather than
# overwriting it wholesale, or every restart would silently wipe that state.
set -e

CONFIG_DIR="${HERMES_HOME:-/home/hermes/.hermes}"
CONFIG="$CONFIG_DIR/config.yaml"
PYTHON="${HERMES_PYTHON:-/opt/hermes-venv/bin/python}"

if [ -n "${HERMES_DEFAULT_PROVIDER:-}" ]; then
  mkdir -p "$CONFIG_DIR"
  "$PYTHON" - "$CONFIG" <<'PYEOF'
import os
import sys

import yaml

config_path = sys.argv[1]

try:
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
except FileNotFoundError:
    config = {}
if not isinstance(config, dict):
    config = {}

model = {"provider": os.environ["HERMES_DEFAULT_PROVIDER"]}
default_model = os.environ.get("HERMES_DEFAULT_MODEL")
if default_model:
    model["default"] = default_model
base_url = os.environ.get("HERMES_DEFAULT_BASE_URL")
if base_url:
    model["base_url"] = base_url
api_mode = os.environ.get("HERMES_DEFAULT_API_MODE")
if api_mode:
    model["api_mode"] = api_mode

# Only these three top-level keys are ever touched here — anything else already
# in the file (mcp_servers, etc.) is preserved untouched.
config["model"] = model
config["web"] = {"use_gateway": True}
config["image_gen"] = {"use_gateway": True}

with open(config_path, "w") as f:
    yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
PYEOF
fi

exec node /opt/agent37-gateway/dist/server/server/index.js
