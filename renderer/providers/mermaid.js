'use strict';

/**
 * Mermaid SSR provider.
 * Renders Mermaid diagram definitions to SVG (or PNG via sharp).
 * Uses jsdom to provide the DOM environment that Mermaid requires.
 */

const sharp = require('sharp');

let _mermaid = null;

function ensureInit() {
  if (_mermaid) return;

  // jsdom must be set up before mermaid is require()'d so that mermaid and
  // its D3 dependency see a valid DOM when they are first evaluated.
  const { JSDOM } = require('jsdom');
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    pretendToBeVisual: true,
  });

  const g = global;
  g.window       = dom.window;
  g.document     = dom.window.document;
  g.navigator    = dom.window.navigator;
  g.DOMParser    = dom.window.DOMParser;
  g.XMLSerializer = dom.window.XMLSerializer;
  g.SVGElement   = dom.window.SVGElement;
  g.HTMLElement  = dom.window.HTMLElement;
  g.Element      = dom.window.Element;
  g.Text         = dom.window.Text;
  g.Event        = dom.window.Event;

  // Some mermaid internals check for MutationObserver
  g.MutationObserver = dom.window.MutationObserver;

  const mod = require('mermaid');
  _mermaid = mod.default || mod;

  _mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: 'default',
    fontFamily: 'sans-serif',
    flowchart: { useMaxWidth: false, htmlLabels: false },
    sequence:  { useMaxWidth: false },
  });
}

async function render({ chart, format = 'png', width = 800, height = 600 }) {
  ensureInit();

  const definition = typeof chart === 'string' ? chart : String(chart);
  const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  // Mermaid.render() needs a real DOM node to attach to during rendering
  const el = global.document.createElement('div');
  el.id = id;
  global.document.body.appendChild(el);

  let svgStr;
  try {
    const result = await _mermaid.render(id, definition);
    // v10+ returns { svg, bindFunctions }; older CJS build returns the string directly
    svgStr = (result && typeof result === 'object' && result.svg) ? result.svg : String(result);
  } finally {
    if (el.parentNode) el.parentNode.removeChild(el);
    // Also clean up the hidden mermaid output element if mermaid left one
    const leftover = global.document.getElementById(`d${id}`);
    if (leftover && leftover.parentNode) leftover.parentNode.removeChild(leftover);
  }

  if (format === 'svg') {
    return Buffer.from(svgStr, 'utf8');
  }

  // PNG: rasterise the SVG with sharp
  return sharp(Buffer.from(svgStr, 'utf8'))
    .resize({ width, height, fit: 'inside', withoutEnlargement: true })
    .png()
    .toBuffer();
}

module.exports = { render };
