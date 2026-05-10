import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

const isPages = process.env.GITHUB_PAGES === '1';
const repo = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? 'Pantanos';

export default defineConfig({
  site: isPages ? `https://${process.env.GITHUB_REPOSITORY?.split('/')[0]}.github.io` : 'http://localhost:4321',
  base: isPages ? `/${repo}/` : '/',
  integrations: [tailwind()],
  output: 'static',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
