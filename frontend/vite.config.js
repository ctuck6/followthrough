import { defineConfig } from 'vite';
export default defineConfig({server:{port:5173,strictPort:true,proxy:{'/api':process.env.FOLLOWTHROUGH_BACKEND||'http://127.0.0.1:8000'}}});
