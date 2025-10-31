import { spawn } from 'child_process';

// Start FastAPI backend
const API_KEY = process.env.API_KEY || "oficinapro2024";
console.log('[Production] Starting FastAPI backend...');

const fastapi = spawn('uvicorn', ['app_oficina:app', '--host', '0.0.0.0', '--port', '8000'], {
  env: { ...process.env, API_KEY },
  stdio: ['ignore', 'pipe', 'pipe']
});

fastapi.stdout.on('data', (data) => {
  console.log(`[FastAPI] ${data.toString().trim()}`);
});

fastapi.stderr.on('data', (data) => {
  const msg = data.toString().trim();
  if (msg.includes('ERROR') || msg.includes('CRITICAL')) {
    console.error(`[FastAPI Error] ${msg}`);
  } else {
    console.log(`[FastAPI] ${msg}`);
  }
});

fastapi.on('close', (code) => {
  if (code !== 0 && code !== null) {
    console.error(`[FastAPI] Process exited with code ${code}`);
    process.exit(1);
  }
});

// Wait for FastAPI to be ready
setTimeout(async () => {
  console.log('[Production] Starting Express server...');
  process.env.FASTAPI_URL = 'http://localhost:8000';
  process.env.API_KEY = API_KEY;
  
  // Import and run the main Express app
  await import('./dist/index.js');
}, 3000);
