const http = require('node:http');
const crypto = require('node:crypto');

const DEFAULT_TTL_SECONDS = 24 * 60 * 60;

function readEnv(name, fallback = '') {
  const value = process.env[name];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function toInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ''), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function respond(res, status, body) {
  res.statusCode = status;
  res.setHeader('content-type', 'text/plain; charset=utf-8');
  res.end(body);
}

function bearerToken(req) {
  const auth = String(req.headers.authorization || '');
  const match = /^Bearer\s+(.+)$/i.exec(auth);
  return match ? match[1].trim() : '';
}

function validateToken(containerId, token, secret, nowSeconds) {
  const dotIndex = token.indexOf('.');
  if (!containerId || dotIndex === -1) return false;

  const expiresHex = token.slice(0, dotIndex);
  const signature = token.slice(dotIndex + 1);
  const expiresAt = Number.parseInt(expiresHex, 16);
  if (!Number.isFinite(expiresAt) || expiresAt < nowSeconds) return false;

  const expected = crypto.createHmac('sha256', secret).update(`${containerId}:${expiresHex}`).digest('hex');
  if (expected.length !== signature.length) return false;

  try {
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

const secret = readEnv('HEADMASTER_FORWARD_AUTH_SECRET') || readEnv('FORWARD_AUTH_HMAC_SECRET');
const port = toInt(readEnv('PORT'), 8080);
const ttlSeconds = toInt(readEnv('HEADMASTER_FORWARD_AUTH_TTL_SECONDS'), DEFAULT_TTL_SECONDS);

if (!secret) {
  console.error('Missing HEADMASTER_FORWARD_AUTH_SECRET');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  if (req.url === '/healthz') return respond(res, 200, 'ok');

  const containerId = String(req.headers['x-headmaster-container-id'] || '').trim();
  const token = bearerToken(req);
  const nowSeconds = Math.floor(Date.now() / 1000);

  if (!containerId || !token) return respond(res, 401, 'Unauthorized');
  if (!validateToken(containerId, token, secret, nowSeconds)) return respond(res, 403, 'Forbidden');

  res.setHeader('x-headmaster-auth-ttl-seconds', String(ttlSeconds));
  return respond(res, 200, 'OK');
});

server.listen(port, '0.0.0.0', () => {
  console.log(`headmaster-forward-auth listening on :${port}`);
});
