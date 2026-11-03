// mock-server.mjs — 构建后单进程服务：:8080 提供 dist 静态文件 + 同一套 /api/v1 mock API。
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { handleApi } from './mock/api.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const DIST = join(ROOT, 'dist');
const PORT = Number(process.env.PORT || 8080);
const HOST = process.env.HOST || '127.0.0.1';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.ico': 'image/x-icon',
  '.map': 'application/json; charset=utf-8',
};

async function serveStatic(req, res, pathname) {
  let filePath = resolve(join(DIST, normalize(decodeURIComponent(pathname))));
  if (!filePath.startsWith(resolve(DIST))) {
    res.statusCode = 403;
    return res.end('Forbidden');
  }
  try {
    const info = await stat(filePath);
    if (info.isDirectory()) filePath = join(filePath, 'index.html');
    const data = await readFile(filePath);
    res.setHeader('Content-Type', MIME[extname(filePath).toLowerCase()] || 'application/octet-stream');
    res.setHeader('Cache-Control', extname(filePath) === '.html' ? 'no-store' : 'public, max-age=3600');
    return res.end(data);
  } catch {
    try {
      const html = await readFile(join(DIST, 'index.html'));
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store');
      return res.end(html);
    } catch {
      res.statusCode = 404;
      return res.end('dist/ not found: run npm run build first, then node mock-server.mjs');
    }
  }
}

const server = createServer(async (req, res) => {
  const started = Date.now();
  res.setHeader('X-Mock-Server', 'qwatch');
  try {
    const handled = await handleApi(req, res);
    if (handled) return;
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.statusCode = 405;
      return res.end('Method Not Allowed');
    }
    const url = new URL(req.url || '/', 'http://localhost');
    await serveStatic(req, res, url.pathname);
  } catch (err) {
    console.error('[mock-server] error:', err);
    if (!res.headersSent) {
      res.statusCode = 500;
      res.end(JSON.stringify({ detail: String((err && err.message) || err) }));
    }
  } finally {
    if (process.env.LOG !== '0') {
      console.log(new Date().toISOString() + ' ' + req.method + ' ' + req.url + ' ' + res.statusCode + ' ' + (Date.now() - started) + 'ms');
    }
  }
});

server.listen(PORT, HOST, () => {
  console.log('');
  console.log('  qwatch mock server');
  console.log('  --------------------------------');
  console.log('  Web : http://' + HOST + ':' + PORT + '  (dist/ static build)');
  console.log('  API : http://' + HOST + ':' + PORT + '/api/v1  (mock)');
  console.log('  Login: password qwatch');
  console.log('  Tip: npm run build first; HOST=0.0.0.0 for LAN access');
  console.log('');
});

process.on('SIGINT', () => { server.close(() => process.exit(0)); });
