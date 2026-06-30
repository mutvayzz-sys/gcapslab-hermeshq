FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_SERVER_ENABLED=true
ENV API_SERVER_HOST=0.0.0.0
ENV API_SERVER_PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "git+https://github.com/NousResearch/hermes-agent.git"

RUN useradd --create-home --shell /bin/bash hermes

# Bake a default runtime config so fresh containers have a working model without
# requiring manual setup. NOUS_API_KEY is injected at runtime by the container
# supervisor; this sets the provider routing and gateway flags.
RUN mkdir -p /home/hermes/.hermes && \
    printf 'model:\n  provider: nous-api\n  base_url: "https://inference-api.nousresearch.com/v1"\nweb:\n  use_gateway: true\nimage_gen:\n  use_gateway: true\n' \
    > /home/hermes/.hermes/config.yaml && \
    chown -R hermes:hermes /home/hermes/.hermes

USER hermes
WORKDIR /home/hermes

EXPOSE 8080

CMD ["hermes", "gateway"]
