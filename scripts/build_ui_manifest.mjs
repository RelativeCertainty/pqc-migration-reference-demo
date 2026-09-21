import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '../apps/pqc-enterprise-demo/wwwroot');
const files = [];
async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || entry.name.endsWith('.map') || entry.isSymbolicLink()) throw new Error('unsafe_ui_asset');
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await visit(path);
    else if (entry.name !== 'asset-manifest.sha256') files.push(path);
  }
}
await visit(root);
const lines = [];
for (const path of files.sort()) {
  const digest = createHash('sha256').update(await readFile(path)).digest('hex');
  lines.push(`${digest}  ${relative(root, path).split(sep).join('/')}`);
}
await writeFile(join(root, 'asset-manifest.sha256'), lines.join('\n') + '\n');
console.log(`UI manifest: ${lines.length} assets; no source maps.`);
