import { mkdir, readdir, copyFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const target = path.resolve(root, 'cloud-functions/api/_vendor');
if (target !== path.join(root, 'cloud-functions', 'api', '_vendor')) {
  throw new Error('Unexpected generated directory');
}
await rm(target, { recursive: true, force: true });
const excluded = new Set(['main.py', 'cli.py', 'scheduler.py']);
await mkdir(path.join(target, 'app'), { recursive: true });
await mkdir(path.join(target, 'data'), { recursive: true });
for (const name of await readdir(path.join(root, 'backend/app'))) {
  if (name.endsWith('.py') && !excluded.has(name)) {
    await copyFile(path.join(root, 'backend/app', name), path.join(target, 'app', name));
  }
}
// Explicit seed allowlist: never copy .env, live DBs, caches or local artifacts.
for (const name of ['papers.toml', 'researchers.toml', 'scholar_reviews.toml']) {
  await copyFile(path.join(root, 'backend/data', name), path.join(target, 'data', name));
}
console.log('Prepared Makers Python code and three seed files.');
