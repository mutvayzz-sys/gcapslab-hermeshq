FROM node:24-alpine

WORKDIR /app
COPY server.js /app/server.js

ENV PORT=8080
ENV HEADMASTER_FORWARD_AUTH_TTL_SECONDS=86400

EXPOSE 8080

CMD ["node", "/app/server.js"]
