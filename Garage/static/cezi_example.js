// Simple helper utilities for idempotent register + retry/backoff
function uuidv4() {
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function postWithRetry(url, body, headers = {}, retries = 3, baseMs = 200) {
    let attempt = 0;
    while (true) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, headers),
                body: JSON.stringify(body),
                credentials: 'include',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw { status: res.status, data };
            return { status: res.status, data };
        } catch (err) {
            attempt++;
            if (attempt > retries) throw err;
            const jitter = Math.random() * 100;
            const wait = baseMs * Math.pow(2, attempt - 1) + jitter;
            appendLog(`retry ${attempt}/${retries} → waiting ${Math.round(wait)}ms`);
            await sleep(wait);
        }
    }
}

function setStatus(text) { document.getElementById('status').innerText = text; }
function appendLog(msg) { const p = document.getElementById('log'); p.innerText = (p.innerText === '—' ? '' : p.innerText + '\n') + msg; }
function showHeaders(h) { document.getElementById('headers').innerText = JSON.stringify(h, null, 2); }

document.getElementById('register').addEventListener('click', async () => {
    const full_name = document.getElementById('full_name').value || 'Teste Cezi';
    const email = document.getElementById('email').value || `test+${Date.now()}@example.com`;
    const username = `u${Date.now().toString(36).slice(-6)}`;
    const whatsapp = document.getElementById('whatsapp')?.value || '5511999999999';
    const profession = document.getElementById('profession')?.value || 'autonomo';
    const password = document.getElementById('password')?.value || 'secret123';
    const idempotencyKey = uuidv4();
    const traceId = uuidv4();
    const headers = {
        'Idempotency-Key': idempotencyKey,
        'x-trace-id': traceId,
    };

    showHeaders(headers);
    appendLog(`Starting register for ${email} (idempotency=${idempotencyKey})`);
    setStatus('Enviando (otimista)...');

    // UI otimista
    const optimisticToken = `optimistic-${Date.now()}`;
    appendLog(`optimistic token: ${optimisticToken}`);

    try {
        const payload = { full_name, username, email, whatsapp, profession, password };
        const res = await postWithRetry('/api/auth/register', payload, headers, 3, 250);
        appendLog(`Success ${res.status}: ${JSON.stringify(res.data)}`);
        setStatus('Registrado — verifique seu e-mail (ou veja logs).');
    } catch (err) {
        appendLog(`Final failure: ${JSON.stringify(err)}`);
        setStatus('Falha ao registrar — rollback do estado otimista.');
    }
});
