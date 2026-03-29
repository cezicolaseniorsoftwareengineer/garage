// Generate a small env bootstrap for Netlify builds.
// Usage in Netlify build command: `node scripts/write_netlify_env.js`
const fs = require('fs');
const path = require('path');

const env = {
    ASAAS_MONTHLY: process.env.FRONT_ASAAS_MONTHLY || process.env.FRONT_ASAAS_MENSAL || '',
    ASAAS_ANNUAL: process.env.FRONT_ASAAS_ANNUAL || process.env.FRONT_ASAAS_ANUAL || ''
};

const out = `window.__ENV__ = ${JSON.stringify(env)};\n`;
const outPath = path.join(__dirname, '..', 'landing', 'env.js');

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, out, 'utf8');
console.log('Wrote', outPath);
