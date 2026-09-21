import { fileURLToPath } from 'node:url';

// Offline tool tests only. This is not a second frontend or application server.
export default {
  root: fileURLToPath(new URL('../', import.meta.url)),
  test: {
    include: ['tools/repository-scanner/**/*.test.ts'],
    environment: 'node',
    globals: true,
    maxWorkers: 1,
  },
};
