'use strict';

const echarts = require('echarts');

// For PNG output we need a canvas backend.
// We register node-canvas lazily so the module can be loaded in environments
// that only need SVG output (no native canvas bindings required).
let canvasBackendRegistered = false;
function ensureCanvasBackend() {
  if (canvasBackendRegistered) return;
  const { createCanvas } = require('canvas');
  echarts.setPlatformAPI({
    createCanvas() {
      return createCanvas(1, 1);
    },
  });
  canvasBackendRegistered = true;
}

const MAX_WIDTH = Number(process.env.CHART_MAX_WIDTH) || 3000;
const MAX_HEIGHT = Number(process.env.CHART_MAX_HEIGHT) || 3000;

async function render(config) {
  const { width = 500, height = 300, backgroundColor, format = 'png' } = config;

  if (width > MAX_WIDTH) throw new Error(`Width exceeds maximum of ${MAX_WIDTH}`);
  if (height > MAX_HEIGHT) throw new Error(`Height exceeds maximum of ${MAX_HEIGHT}`);

  let chartConfig = config.chart;
  if (typeof chartConfig === 'string') {
    try {
      chartConfig = new Function(`return ${chartConfig}`)();
    } catch (err) {
      throw new Error(`Invalid ECharts config: ${err.message}`);
    }
  }

  // Inject background color into ECharts config if supplied and not already set
  if (backgroundColor && !chartConfig.backgroundColor) {
    chartConfig = { backgroundColor, ...chartConfig };
  }

  if (format === 'svg') {
    // Zero-dependency SVG path — no canvas bindings needed
    const chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width, height });
    chart.setOption(chartConfig);
    const svg = chart.renderToSVGString();
    chart.dispose();
    return Buffer.from(svg, 'utf8');
  }

  // PNG path — requires node-canvas
  ensureCanvasBackend();
  const { createCanvas } = require('canvas');
  const nodeCanvas = createCanvas(width, height);
  const chart = echarts.init(nodeCanvas, null, { renderer: 'canvas', width, height });
  chart.setOption(chartConfig);

  return new Promise((resolve, reject) => {
    try {
      const buf = nodeCanvas.toBuffer('image/png');
      chart.dispose();
      resolve(buf);
    } catch (err) {
      reject(err);
    }
  });
}

module.exports = { render };
