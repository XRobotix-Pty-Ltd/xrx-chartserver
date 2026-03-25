'use strict';

const express = require('express');
const chartjs   = require('./providers/chartjs');
const echarts    = require('./providers/echarts');
const mermaid    = require('./providers/mermaid');
const plantuml   = require('./providers/plantuml');

const app = express();
app.use(express.json({ limit: '4mb' }));

const PROVIDERS = { chartjs, echarts, mermaid, plantuml };

const FORMAT_CONTENT_TYPE = {
  png: 'image/png',
  svg: 'image/svg+xml',
};

app.get('/health', (_req, res) => res.json({ ok: true }));

app.post('/render', async (req, res) => {
  const { provider = 'chartjs', format = 'png', width, height, backgroundColor, devicePixelRatio, version, chart } = req.body;

  const providerModule = PROVIDERS[provider];
  if (!providerModule) {
    return res.status(400).json({ error: `Unknown provider: ${provider}. Available: ${Object.keys(PROVIDERS).join(', ')}` });
  }

  if (!chart) {
    return res.status(400).json({ error: 'Missing required field: chart' });
  }

  const fmt = format === 'svg' ? 'svg' : 'png';
  const contentType = FORMAT_CONTENT_TYPE[fmt];

  try {
    const buffer = await providerModule.render({
      chart,
      format: fmt,
      width: Number(width) || 500,
      height: Number(height) || 300,
      backgroundColor,
      devicePixelRatio: Number(devicePixelRatio) || 2,
      version: String(version || '2'),
    });
    res.set('Content-Type', contentType);
    res.send(buffer);
  } catch (err) {
    res.status(422).json({ error: err.message || String(err) });
  }
});

const PORT = Number(process.env.RENDERER_PORT) || 3401;
app.listen(PORT, '127.0.0.1', () => {
  console.log(`Renderer listening on 127.0.0.1:${PORT}`);
});

module.exports = app;
