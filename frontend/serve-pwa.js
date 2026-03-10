#!/usr/bin/env node

/**
 * Simple HTTP server to test PWA builds
 * Serves the production builds with proper MIME types
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8080;
const APP = process.argv[2] || 'form'; // 'admin' or 'form'
const ROOT_DIR = path.join(__dirname, 'dist', APP, 'browser');

const MIME_TYPES = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
};

const server = http.createServer((req, res) => {
  let filePath = path.join(ROOT_DIR, req.url === '/' ? 'index.html' : req.url);
  
  // Security: prevent directory traversal
  if (!filePath.startsWith(ROOT_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === 'ENOENT') {
        // Serve index.html for client-side routing
        fs.readFile(path.join(ROOT_DIR, 'index.html'), (err, data) => {
          if (err) {
            res.writeHead(500);
            res.end('Error loading index.html');
          } else {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(data);
          }
        });
      } else {
        res.writeHead(500);
        res.end('Server error');
      }
    } else {
      const ext = path.extname(filePath);
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      
      res.writeHead(200, { 
        'Content-Type': contentType,
        'Cache-Control': 'no-cache'
      });
      res.end(data);
    }
  });
});

server.listen(PORT, () => {
  console.log(`\n🚀 PWA Server running for ${APP} app`);
  console.log(`📱 Open: http://localhost:${PORT}`);
  console.log(`📊 Test PWA: npx lighthouse http://localhost:${PORT} --view --only-categories=pwa\n`);
});

