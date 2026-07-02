FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=3737
ENV HOST=0.0.0.0
ENV GATEWAY_DEFAULT_AGENT=hermes
ENV HERMES_HOME=/home/hermes/.hermes
ENV HERMES_AGENT_DIR=/opt/hermes-agent
ENV HERMES_PYTHON=/opt/hermes-venv/bin/python
ENV AGENT37_GATEWAY_HOME=/home/hermes/.agent37-gateway
ENV GATEWAY_WORKSPACE_DIR=/home/hermes/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    rsync \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent \
    && python3 -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/hermes-venv/bin/pip install -e "/opt/hermes-agent[anthropic]"

WORKDIR /opt/agent37-gateway
COPY third_party/agent37/gateway/package*.json ./
RUN npm ci
COPY third_party/agent37/gateway/ ./
RUN npm run build && npm prune --omit=dev

# Only /home/hermes needs hermes ownership — nothing writes under /opt at runtime,
# and the pip/npm-installed trees are world-readable. Chowning the multi-GB venv
# made rebuilds take tens of minutes; scope it to /home/hermes instead.
RUN useradd --create-home --shell /bin/bash hermes \
    && mkdir -p /home/hermes/.hermes /home/hermes/.agent37-gateway /home/hermes/workspace \
    && printf 'model:\n  provider: nous-api\n  base_url: "https://inference-api.nousresearch.com/v1"\nweb:\n  use_gateway: true\nimage_gen:\n  use_gateway: true\n' > /home/hermes/.hermes/config.yaml \
    && chown -R hermes:hermes /home/hermes

# Entrypoint copied last so editing it never re-runs the steps above.
COPY --chown=hermes:hermes backend/runtime-entrypoint.sh /opt/runtime-entrypoint.sh
RUN chmod +x /opt/runtime-entrypoint.sh

USER hermes
WORKDIR /home/hermes/workspace

EXPOSE 3737

# Entrypoint generates config.yaml from the injected provider env, then starts the gateway.
CMD ["/opt/runtime-entrypoint.sh"]
