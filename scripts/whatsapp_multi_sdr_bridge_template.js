/*
 * whatsapp_multi_sdr_bridge_template.js — MVP seguro de bridge WhatsApp por porta/SDR.
 *
 * NÃO substitui nem reinicia o bridge vivo. Este arquivo é um template project-side
 * para rodar uma instância nova/controlada quando for migrar com janela segura.
 *
 * Dependências esperadas: as mesmas do whatsapp-extra/single-extra.js:
 *   @whiskeysockets/baileys, pino, qrcode
 *
 * Exemplo futuro (não execute em porta viva sem planejamento):
 *   WPP_BRIDGE_TOKEN='token-forte' node scripts/whatsapp_multi_sdr_bridge_template.js \
 *     --port 4610 --auth ./controle/wpp_auth_4610 --sdr Lucas
 *
 * Logs/histórico:
 *   controle/wpp_channel_logs/port-<PORT>.jsonl
 *   controle/wpp_channel_media/<PORT>/...
 *
 * Endpoints:
 *   GET  /status
 *   GET  /qr | /qr.png
 *   GET  /me
 *   GET  /history?limit=200&t=<token>
 *   POST /send       {to,text}
 *   POST /send-file  {to,filePath,fileName,mimetype,caption,thumbnailPath}
 *   POST /send-media {to,filePath,mimetype,caption,fileName,asDocument?}
 *   POST /send-audio {to,filePath,mimetype,ptt?}
 */
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const pino = require('pino');
const path = require('path');
const fs = require('fs');
const http = require('http');
const crypto = require('crypto');
const QRCode = require('qrcode');

const args = process.argv.slice(2);
function getArg(name, fallback) {
  const idx = args.indexOf(name);
  if (idx !== -1 && idx + 1 < args.length) return args[idx + 1];
  return fallback;
}
function hasArg(name) { return args.includes(name); }

const PROJECT_DIR = path.resolve(__dirname, '..');
const PORT = parseInt(getArg('--port', process.env.WPP_PORT || '4610'), 10);
const SDR = getArg('--sdr', process.env.WPP_SDR || `port-${PORT}`);
const AUTH_DIR = path.resolve(getArg('--auth', process.env.WPP_AUTH_DIR || path.join(PROJECT_DIR, 'controle', `wpp_auth_${PORT}`)));
const LOG_DIR = path.resolve(getArg('--log-dir', process.env.WPP_LOG_DIR || path.join(PROJECT_DIR, 'controle', 'wpp_channel_logs')));
const MEDIA_DIR = path.resolve(getArg('--media-dir', process.env.WPP_MEDIA_DIR || path.join(PROJECT_DIR, 'controle', 'wpp_channel_media', String(PORT))));
const TOKEN = getArg('--token', process.env.WPP_BRIDGE_TOKEN || '');
const HOST = getArg('--host', process.env.WPP_HOST || '127.0.0.1');
const MAX_BODY = parseInt(getArg('--max-body', process.env.WPP_MAX_BODY || String(25 * 1024 * 1024)), 10);
const ALLOW_REGEN = hasArg('--allow-regen') || process.env.WPP_ALLOW_REGEN === '1';
const HISTORY_FILE = path.join(LOG_DIR, `port-${PORT}.jsonl`);

let sock = null;
let lastQR = null;
let connected = false;
let reconnectCount = 0;
let me = null;

function nowIso() { return new Date().toISOString(); }
function ensureDirs() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  fs.mkdirSync(LOG_DIR, { recursive: true });
  fs.mkdirSync(MEDIA_DIR, { recursive: true });
}
function safeJson(obj) { return JSON.stringify(obj, (_, v) => typeof v === 'bigint' ? String(v) : v); }
function appendEvent(event) {
  ensureDirs();
  const row = {
    ts: nowIso(),
    port: PORT,
    sdr: SDR,
    ...event,
  };
  fs.appendFileSync(HISTORY_FILE, safeJson(row) + '\n', { encoding: 'utf8' });
  return row;
}
function json(res, code, obj) {
  res.statusCode = code;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(obj));
}
function html(res, code, body) {
  res.statusCode = code;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(body);
}
function tokenFromReq(req, parsedUrl) {
  const h = req.headers['x-bridge-token'] || req.headers['authorization'] || '';
  if (String(h).startsWith('Bearer ')) return String(h).slice(7);
  if (h) return String(h);
  return parsedUrl.searchParams.get('t') || parsedUrl.searchParams.get('token') || '';
}
function authorized(req, parsedUrl) {
  if (!TOKEN) return true; // modo local/dev; em produção defina WPP_BRIDGE_TOKEN
  const got = tokenFromReq(req, parsedUrl);
  try {
    return got.length === TOKEN.length && crypto.timingSafeEqual(Buffer.from(got), Buffer.from(TOKEN));
  } catch { return false; }
}
function jidFor(to) {
  const s = String(to || '').trim();
  if (!s) return '';
  if (s.includes('@')) return s;
  const digits = s.replace(/\D/g, '');
  if (!digits) return '';
  return `${digits}@s.whatsapp.net`;
}
function guessMime(filePath, fallback) {
  if (fallback) return fallback;
  const ext = path.extname(filePath).toLowerCase();
  return ({
    '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.webp': 'image/webp', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
    '.opus': 'audio/ogg', '.wav': 'audio/wav', '.txt': 'text/plain', '.csv': 'text/csv',
  })[ext] || 'application/octet-stream';
}
function messageText(msg) {
  const m = msg.message || {};
  return m.conversation || m.extendedTextMessage?.text || m.imageMessage?.caption || m.videoMessage?.caption || m.documentMessage?.caption || '';
}
function messageKind(msg) {
  const m = msg.message || {};
  return Object.keys(m)[0] || 'unknown';
}
function mediaExt(kind, mime) {
  const byMime = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'video/mp4': '.mp4', 'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'application/pdf': '.pdf'};
  if (byMime[mime]) return byMime[mime];
  if (kind.includes('image')) return '.bin';
  if (kind.includes('video')) return '.mp4';
  if (kind.includes('audio')) return '.ogg';
  if (kind.includes('document')) return '.dat';
  return '.bin';
}
async function maybeDownloadMedia(msg, kind) {
  try {
    const m = msg.message || {};
    const node = m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage;
    if (!node) return null;
    const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger: pino({ level: 'silent' }) });
    const mime = node.mimetype || '';
    const id = msg.key?.id || crypto.randomBytes(8).toString('hex');
    const fileName = `${Date.now()}_${String(id).replace(/[^a-zA-Z0-9_.-]/g, '_')}${mediaExt(kind, mime)}`;
    const fullPath = path.join(MEDIA_DIR, fileName);
    fs.writeFileSync(fullPath, buffer);
    return { path: fullPath, bytes: buffer.length, mimetype: mime, fileName };
  } catch (err) {
    return { error: err.message };
  }
}
function readHistory(limit) {
  if (!fs.existsSync(HISTORY_FILE)) return [];
  const lines = fs.readFileSync(HISTORY_FILE, 'utf8').trim().split('\n').filter(Boolean);
  return lines.slice(-limit).map((line) => { try { return JSON.parse(line); } catch { return { raw: line }; } });
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (c) => {
      body += c.toString();
      if (Buffer.byteLength(body) > MAX_BODY) {
        reject(new Error('Body too large'));
        try { req.destroy(); } catch {}
      }
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}
async function parseJsonBody(req) {
  const raw = await readBody(req);
  return raw ? JSON.parse(raw) : {};
}
async function connect() {
  ensureDirs();
  console.log(`[WPP-MVP ${PORT}] Iniciando conexão auth=${AUTH_DIR}`);
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  sock = makeWASocket({
    auth: state,
    logger: pino({ level: 'silent' }),
    printQRInTerminal: false,
    browser: [`Zydon-${SDR}`, 'Chrome', '1.0'],
  });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      lastQR = qr; connected = false;
      appendEvent({ direction: 'system', type: 'qr', event: 'qr_generated' });
      console.log(`[WPP-MVP ${PORT}] QR gerado — acesse /qr`);
    }
    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      connected = false; me = null; reconnectCount += 1;
      appendEvent({ direction: 'system', type: 'connection', event: 'close', code, reconnect: shouldReconnect, reconnectCount });
      if (code === DisconnectReason.loggedOut || code === 401) {
        lastQR = null;
        if (fs.existsSync(AUTH_DIR)) fs.rmSync(AUTH_DIR, { recursive: true, force: true });
      }
      if (shouldReconnect || code === 401) setTimeout(connect, 3000);
    } else if (connection === 'open') {
      lastQR = null; connected = true; reconnectCount = 0; me = sock.user || null;
      appendEvent({ direction: 'system', type: 'connection', event: 'open', me });
      console.log(`[WPP-MVP ${PORT}] CONECTADO SDR=${SDR}`);
    }
  });
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    for (const msg of messages || []) {
      if (!msg.message) continue;
      const fromMe = !!msg.key?.fromMe;
      const kind = messageKind(msg);
      const media = await maybeDownloadMedia(msg, kind);
      appendEvent({
        direction: fromMe ? 'out' : 'in',
        source: 'whatsapp',
        upsertType: type,
        type: kind,
        id: msg.key?.id,
        remoteJid: msg.key?.remoteJid,
        participant: msg.key?.participant,
        fromMe,
        pushName: msg.pushName,
        text: messageText(msg),
        messageTimestamp: msg.messageTimestamp ? String(msg.messageTimestamp) : null,
        media,
      });
    }
  });
}

const server = http.createServer(async (req, res) => {
  const parsed = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
  const p = parsed.pathname;
  res.setHeader('X-Robots-Tag', 'noindex, nofollow');

  if (p === '/status') {
    return json(res, 200, { connected, needsQR: !!lastQR, hasAuth: fs.existsSync(AUTH_DIR) && fs.readdirSync(AUTH_DIR).length > 0, reconnectCount, port: PORT, sdr: SDR, tokenEnabled: !!TOKEN });
  }
  if ((p === '/qr' || p === '/qr.png') && lastQR) {
    if (!authorized(req, parsed)) return json(res, 403, { error: 'forbidden' });
    if (p === '/qr.png') {
      const png = await QRCode.toBuffer(lastQR, { width: 500 });
      res.statusCode = 200; res.setHeader('Content-Type', 'image/png'); return res.end(png);
    }
    const dataUrl = await QRCode.toDataURL(lastQR, { width: 460 });
    return html(res, 200, `<html><body style="display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#101820;color:#fff;font-family:sans-serif"><div style="text-align:center"><h2>WhatsApp ${SDR} — porta ${PORT}</h2><img src="${dataUrl}" style="border-radius:12px"/><p>Use apenas em migração planejada.</p></div></body></html>`);
  }
  if (p === '/me') return json(res, connected ? 200 : 503, { connected, me: me || sock?.user || null });
  if (p === '/history') {
    if (!authorized(req, parsed)) return json(res, 403, { error: 'forbidden' });
    const limit = Math.max(1, Math.min(1000, parseInt(parsed.searchParams.get('limit') || '200', 10)));
    return json(res, 200, { port: PORT, sdr: SDR, items: readHistory(limit) });
  }
  if (req.method === 'POST' && p === '/regen') {
    if (!ALLOW_REGEN) return json(res, 403, { error: 'regen disabled; start with --allow-regen or WPP_ALLOW_REGEN=1' });
    if (!authorized(req, parsed)) return json(res, 403, { error: 'forbidden' });
    lastQR = null; connected = false; me = null;
    if (sock) try { sock.end(); } catch {}
    if (fs.existsSync(AUTH_DIR)) fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    appendEvent({ direction: 'system', type: 'regen', event: 'requested' });
    setTimeout(connect, 1500);
    return json(res, 200, { regenerating: true });
  }
  if (req.method === 'POST' && ['/send', '/send-file', '/send-media', '/send-audio'].includes(p)) {
    if (!authorized(req, parsed)) return json(res, 403, { error: 'forbidden' });
    if (!sock || !connected) return json(res, 503, { error: 'Not connected' });
    try {
      const body = await parseJsonBody(req);
      const to = jidFor(body.to);
      if (!to) return json(res, 400, { error: 'Missing/invalid to' });
      let payload;
      if (p === '/send') {
        if (!body.text) return json(res, 400, { error: 'Missing text' });
        payload = { text: String(body.text) };
      } else {
        if (!body.filePath) return json(res, 400, { error: 'Missing filePath' });
        const filePath = path.resolve(String(body.filePath));
        if (!fs.existsSync(filePath)) return json(res, 404, { error: 'File not found' });
        const fileBuffer = fs.readFileSync(filePath);
        const mimetype = guessMime(filePath, body.mimetype);
        const fileName = body.fileName || path.basename(filePath);
        if (p === '/send-audio') payload = { audio: fileBuffer, mimetype, ptt: body.ptt !== false };
        else if (p === '/send-media' && !body.asDocument && mimetype.startsWith('image/')) payload = { image: fileBuffer, mimetype, caption: body.caption || undefined };
        else if (p === '/send-media' && !body.asDocument && mimetype.startsWith('video/')) payload = { video: fileBuffer, mimetype, caption: body.caption || undefined };
        else payload = { document: fileBuffer, mimetype, fileName, caption: body.caption || undefined };
        if (body.thumbnailPath && fs.existsSync(body.thumbnailPath)) payload.jpegThumbnail = fs.readFileSync(body.thumbnailPath);
      }
      const result = await sock.sendMessage(to, payload);
      const event = appendEvent({ direction: 'out', source: 'api', type: p.slice(1), remoteJid: to, text: body.text || body.caption || '', filePath: body.filePath || null, id: result?.key?.id, status: result?.status });
      return json(res, 200, { success: true, messageId: result?.key?.id, status: result?.status, event });
    } catch (err) {
      appendEvent({ direction: 'system', type: 'error', endpoint: p, error: err.message });
      return json(res, 500, { error: err.message });
    }
  }
  return json(res, 404, { error: 'Not Found', endpoints: ['GET /status', 'GET /qr', 'GET /qr.png', 'GET /me', 'GET /history', 'POST /send', 'POST /send-file', 'POST /send-media', 'POST /send-audio'] });
});

ensureDirs();
server.listen(PORT, HOST, () => {
  console.log(`[WPP-MVP ${PORT}] HTTP em http://${HOST}:${PORT} token=${TOKEN ? 'on' : 'off/dev'} log=${HISTORY_FILE}`);
  connect();
});
