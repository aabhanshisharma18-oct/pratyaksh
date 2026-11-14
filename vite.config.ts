import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({mode}) => {
  const detectionTarget = loadEnv(mode, '.').VITE_D1_API_BASE_URL?.trim();
  const caseTarget = loadEnv(mode, '.').VITE_API_BASE_URL?.trim();
  const workspaceTarget = caseTarget || 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    build: {outDir: 'dist'},
    server: {
      proxy: {
        '/api/evidence': 'http://127.0.0.1:8001',
        '/d2': {target: workspaceTarget, changeOrigin: true},
        '/api/d2': {target: workspaceTarget, changeOrigin: true},
        ...(caseTarget && {'/api/reports': {target: caseTarget, changeOrigin: true},'/api/findings': {target: caseTarget, changeOrigin: true},'/api/cases': {target: caseTarget, changeOrigin: true}}),
        ...(detectionTarget && {'/api/d1/': {target: detectionTarget, changeOrigin: true}}),
      },
    },
  };
});
