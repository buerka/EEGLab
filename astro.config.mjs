import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import { parse as parseToml } from 'smol-toml';

export default defineConfig({
  integrations: [react()],
  vite: {
    plugins: [{
      name: 'vite-toml',
      transform(src, id) {
        if (!id.endsWith('.toml')) return null;
        return { code: `export default ${JSON.stringify(parseToml(src))}`, map: null };
      },
    }],
  },
});
