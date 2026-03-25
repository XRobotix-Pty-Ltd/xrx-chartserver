'use strict';

const canvas = require('canvas');
const deepmerge = require('deepmerge');
const pattern = require('patternomaly');
const { CanvasRenderService } = require('chartjs-node-canvas');

require('canvas-5-polyfill');
global.CanvasGradient = canvas.CanvasGradient;

// Pre-register chartjs-chart-sankey for both v3 and v4.
// The plugin uses require('chart.js') internally so we hook module resolution
// to redirect to the aliased packages before loading it for each version.
(function registerSankeyPlugin() {
  const Module = require('module');
  const origResolveFilename = Module._resolveFilename;
  const origLoad = Module._load;
  const sankeyPath = require.resolve('chartjs-chart-sankey');

  ['chart.js-v3', 'chart.js-v4'].forEach((prefix, i) => {
    if (i > 0) delete require.cache[sankeyPath];
    Module._resolveFilename = function (request, parent, ...args) {
      if (request === 'chart.js') return origResolveFilename.call(this, prefix, parent, ...args);
      if (request === 'chart.js/helpers')
        return origResolveFilename.call(this, `${prefix}/helpers`, parent, ...args);
      return origResolveFilename.call(this, request, parent, ...args);
    };
    Module._load = function (request, parent, isMain) {
      if (parent && parent.filename === sankeyPath) {
        if (request === 'chart.js') return require(prefix);
        if (request === 'chart.js/helpers') return require(`${prefix}/helpers`);
      }
      return origLoad.call(this, request, parent, isMain);
    };
    require('chartjs-chart-sankey');
  });
  Module._resolveFilename = origResolveFilename;
  Module._load = origLoad;
})();

const ROUND_CHART_TYPES = new Set([
  'pie',
  'doughnut',
  'polarArea',
  'outlabeledPie',
  'outlabeledDoughnut',
]);
const BOXPLOT_CHART_TYPES = new Set(['boxplot', 'horizontalBoxplot', 'violin', 'horizontalViolin']);

const MAX_WIDTH = Number(process.env.CHART_MAX_WIDTH) || 3000;
const MAX_HEIGHT = Number(process.env.CHART_MAX_HEIGHT) || 3000;

const rendererCache = {};

function getChartJs(version) {
  if (version && version.startsWith('4')) return require('chart.js-v4/auto').Chart;
  if (version && version.startsWith('3')) return require('chart.js-v3');
  return require('chart.js');
}

function getRenderer(width, height, version, format) {
  if (width > MAX_WIDTH) throw new Error(`Width exceeds maximum of ${MAX_WIDTH}`);
  if (height > MAX_HEIGHT) throw new Error(`Height exceeds maximum of ${MAX_HEIGHT}`);
  const key = `${width}__${height}__${version}__${format}`;
  if (!rendererCache[key]) {
    const Chart = getChartJs(version);
    rendererCache[key] = new CanvasRenderService(width, height, undefined, format, () => Chart);
  }
  return rendererCache[key];
}

function uniqueSvg(svg) {
  const id = Math.random().toString(36).slice(2, 12);
  return svg
    .replace(/id="clip/g, `id="${id}__clip`)
    .replace(/clip-path="url\(#clip/g, `clip-path="url(#${id}__clip`);
}

function addColorsPlugin(chart) {
  if (chart.options && chart.options.plugins && chart.options.plugins.colorschemes) return;
  chart.options = deepmerge.all([
    {},
    chart.options,
    { plugins: { colorschemes: { scheme: 'tableau.Tableau10' } } },
  ]);
}

function getGradientFunctions(width, height) {
  const getGradientFill = (colorOptions, linearGradient = [0, 0, width, 0]) => {
    return function () {
      const ctx = canvas.createCanvas(20, 20).getContext('2d');
      const grad = ctx.createLinearGradient(...linearGradient);
      colorOptions.forEach(o => grad.addColorStop(o.offset, o.color));
      return grad;
    };
  };
  const getGradientFillHelper = (direction, colors, dimensions = {}) => {
    const colorOptions = colors.map((color, idx) => ({
      color,
      offset: idx / (colors.length - 1 || 1),
    }));
    let linearGradient = [0, 0, dimensions.width || width, 0];
    if (direction === 'vertical') linearGradient = [0, 0, 0, dimensions.height || height];
    else if (direction === 'both')
      linearGradient = [0, 0, dimensions.width || width, dimensions.height || height];
    return getGradientFill(colorOptions, linearGradient);
  };
  return { getGradientFill, getGradientFillHelper };
}

function patternDraw(shapeType, backgroundColor, patternColor, requestedSize) {
  return function () {
    const size = Math.min(200, requestedSize) || 20;
    global.document = { createElement: () => canvas.createCanvas(size, size) };
    return pattern.draw(shapeType, backgroundColor, patternColor, size);
  };
}

async function render(config) {
  const { width = 500, height = 300, backgroundColor, devicePixelRatio, version = '2', format = 'png' } = config;

  let chart = config.chart;

  // Evaluate JS string configs (supports gradients, patterns, etc.)
  if (typeof chart === 'string') {
    try {
      const { getGradientFill, getGradientFillHelper } = getGradientFunctions(width, height);
      const fn = new Function(
        'getGradientFill',
        'getGradientFillHelper',
        'pattern',
        'Chart',
        `return ${chart}`,
      );
      chart = fn(getGradientFill, getGradientFillHelper, { draw: patternDraw }, getChartJs(version));
    } catch (err) {
      throw new Error(`Invalid chart config: ${err.message}`);
    }
  }

  chart.options = chart.options || {};

  // Type aliases and compat fixes
  if (chart.type === 'donut') chart.type = 'doughnut';
  if (chart.type === 'gauge') chart.type = 'radialGauge';
  if (chart.type === 'radialGauge' && version && !version.startsWith('2')) version = '2';
  if (chart.type === 'horizontalBar' && (version.startsWith('3') || version.startsWith('4'))) {
    chart.type = 'bar';
    chart.options.indexAxis = 'y';
  }

  // Sparkline
  if (chart.type === 'sparkline') {
    if (!chart.data.datasets || chart.data.datasets.length < 1)
      throw new Error('"sparkline" requires 1 dataset');
    chart.type = 'line';
    const dataseries = chart.data.datasets[0].data;
    if (!chart.data.labels) chart.data.labels = Array(dataseries.length);
    chart.options.legend = chart.options.legend || { display: false };
    chart.options.elements = chart.options.elements || {};
    chart.options.elements.line = chart.options.elements.line || { borderColor: '#000', borderWidth: 1 };
    chart.options.elements.point = chart.options.elements.point || { radius: 0 };
    chart.options.scales = chart.options.scales || {};
    let min = Infinity, max = -Infinity;
    dataseries.forEach(dp => { min = Math.min(min, dp); max = Math.max(max, dp); });
    chart.options.scales.xAxes = chart.options.scales.xAxes || [{ display: false }];
    chart.options.scales.yAxes = chart.options.scales.yAxes || [
      { display: false, ticks: { min: min - min * 0.05, max: max + max * 0.05 } },
    ];
  }

  // Progress bar
  if (chart.type === 'progressBar') {
    chart.type = 'horizontalBar';
    if (chart.data.datasets.length < 1 || chart.data.datasets.length > 2)
      throw new Error('progressBar requires 1 or 2 datasets');
    const dataLen = chart.data.datasets[0].data.length;
    const usePercentage = chart.data.datasets.length === 1;
    if (usePercentage) chart.data.datasets.push({ data: Array(dataLen).fill(100) });
    if (chart.data.datasets[0].data.length !== chart.data.datasets[1].data.length)
      throw new Error('progressBar datasets must have the same length');
    chart.data.labels = chart.labels || Array.from(Array(dataLen).keys());
    chart.data.datasets[1].backgroundColor = chart.data.datasets[1].backgroundColor || '#fff';
    chart.data.datasets[1].borderColor = chart.data.datasets[1].borderColor || '#4e78a7';
    chart.data.datasets[1].borderWidth = chart.data.datasets[1].borderWidth || 1;
    chart.options = deepmerge(
      {
        legend: { display: false },
        scales: {
          xAxes: [{ ticks: { display: false, beginAtZero: true }, gridLines: { display: false, drawTicks: false } }],
          yAxes: [{ stacked: true, ticks: { display: false }, gridLines: { display: false, drawTicks: false, mirror: true } }],
        },
        plugins: {
          datalabels: {
            color: '#fff',
            formatter: val => (usePercentage ? `${val}%` : val),
            display: ctx => ctx.datasetIndex === 0,
          },
        },
      },
      chart.options,
    );
  }

  chart.options.devicePixelRatio = devicePixelRatio || 2.0;

  // Default scales and color scheme
  if (['bar', 'horizontalBar', 'line', 'scatter', 'bubble'].includes(chart.type)) {
    if (!chart.options.scales)
      chart.options.scales = { yAxes: [{ ticks: { beginAtZero: true } }] };
    addColorsPlugin(chart);
  } else if (['radar', 'scatter', 'bubble'].includes(chart.type) || ROUND_CHART_TYPES.has(chart.type)) {
    addColorsPlugin(chart);
  }

  if (chart.type === 'line' && chart.data && chart.data.datasets) {
    chart.data.datasets.forEach(ds => { ds.lineTension = ds.lineTension || 0; });
  }

  chart.options.plugins = chart.options.plugins || {};
  if (!chart.options.plugins.datalabels) {
    chart.options.plugins.datalabels = {
      display: chart.type === 'pie' || chart.type === 'doughnut',
    };
  }

  // Round chart type plugins (v2 only)
  if (ROUND_CHART_TYPES.has(chart.type) || chart.type === 'radialGauge') {
    global.Chart = require('chart.js');
    require('chartjs-plugin-piechart-outlabels');
    if (chart.type === 'doughnut' || chart.type === 'outlabeledDoughnut')
      require('chartjs-plugin-doughnutlabel');
    let userSpecifiedOutlabels = false;
    chart.data.datasets.forEach(dataset => {
      if (dataset.outlabels || chart.options.plugins.outlabels) userSpecifiedOutlabels = true;
      else dataset.outlabels = { display: false };
    });
    if (userSpecifiedOutlabels) chart.options.plugins.datalabels = { display: false };
  }

  if (chart.options && chart.options.plugins && chart.options.plugins.colorschemes) {
    global.Chart = require('chart.js');
    require('chartjs-plugin-colorschemes');
  }

  if (version.startsWith('3') || version.startsWith('4')) {
    require('chartjs-adapter-moment');
  }

  if (!chart.plugins) {
    if (version.startsWith('3') || version.startsWith('4')) {
      chart.plugins = [];
    } else {
      const chartAnnotations = require('chartjs-plugin-annotation');
      const chartDataLabels = require('chartjs-plugin-datalabels');
      const chartRadialGauge = require('chartjs-chart-radial-gauge');
      const chartBoxViolinPlot = require('chartjs-chart-box-and-violin-plot');
      chart.plugins = [chartDataLabels, chartAnnotations];
      if (chart.type === 'radialGauge') chart.plugins.push(chartRadialGauge);
      if (BOXPLOT_CHART_TYPES.has(chart.type)) chart.plugins.push(chartBoxViolinPlot);
    }
  }

  // Background fill plugin
  chart.plugins.push({
    id: 'background',
    beforeDraw: chartInstance => {
      if (backgroundColor) {
        const c = chartInstance.chart || chartInstance;
        c.ctx.fillStyle = backgroundColor;
        c.ctx.fillRect(0, 0, c.width, c.height);
      }
    },
  });

  if (chart.options.plugins.padBelowLegend) {
    chart.plugins.push({
      id: 'padBelowLegend',
      beforeInit: (chartInstance, val) => {
        global.Chart.Legend.prototype.afterFit = function () {
          this.height = this.height + (Number(val) || 0);
        };
      },
    });
  }

  const renderer = getRenderer(width, height, version, format);
  if (format === 'svg') {
    return Buffer.from(uniqueSvg(renderer.renderToBufferSync(chart, 'image/svg+xml').toString()));
  }
  return renderer.renderToBuffer(chart);
}

module.exports = { render };
