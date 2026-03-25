'use strict';

/**
 * PlantUML renderer provider.
 * Pipes diagram source through the PlantUML JAR via stdin/stdout.
 * Requires Java and the plantuml.jar on the host / in the container.
 *
 * Environment variables:
 *   PLANTUML_JAR  – path to plantuml.jar  (default: /opt/plantuml/plantuml.jar)
 *   JAVA_BIN      – java executable path   (default: java)
 */

const { spawn } = require('child_process');

const PLANTUML_JAR = process.env.PLANTUML_JAR || '/opt/plantuml/plantuml.jar';
const JAVA_BIN     = process.env.JAVA_BIN     || 'java';

async function render({ chart, format = 'png' }) {
  const definition = typeof chart === 'string' ? chart : String(chart);
  const fmt        = format === 'svg' ? '-tsvg' : '-tpng';

  return new Promise((resolve, reject) => {
    const args = [
      '-jar', PLANTUML_JAR,
      fmt,
      '-pipe',
      '-charset', 'UTF-8',
    ];

    let proc;
    try {
      proc = spawn(JAVA_BIN, args, { timeout: 30000 });
    } catch (spawnErr) {
      return reject(new Error(`Failed to spawn Java: ${spawnErr.message}`));
    }

    const stdoutChunks = [];
    const stderrChunks = [];

    proc.stdout.on('data', (chunk) => stdoutChunks.push(chunk));
    proc.stderr.on('data', (chunk) => stderrChunks.push(chunk));

    proc.on('error', (err) => {
      if (err.code === 'ENOENT') {
        reject(new Error(
          'Java not found. PlantUML rendering requires Java to be installed. ' +
          `Tried: ${JAVA_BIN}`
        ));
      } else {
        reject(new Error(`PlantUML process error: ${err.message}`));
      }
    });

    proc.on('close', (code) => {
      const output   = Buffer.concat(stdoutChunks);
      const errText  = Buffer.concat(stderrChunks).toString('utf8');

      if (code !== 0) {
        return reject(new Error(
          `PlantUML exited with code ${code}: ${errText.slice(0, 500)}`
        ));
      }

      if (output.length === 0) {
        return reject(new Error(
          'PlantUML produced no output — check diagram syntax.'
        ));
      }

      resolve(output);
    });

    proc.stdin.write(definition, 'utf8');
    proc.stdin.end();
  });
}

module.exports = { render };
