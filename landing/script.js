/* ═══════════════════════════════════════════════════════════════
   404 GARAGE — Landing Page Scripts
   Bio Code Technology Ltda
═══════════════════════════════════════════════════════════════ */

// ── SERVER DETECTION (Five Server dev vs FastAPI prod) ─────────────
// Ports where FastAPI may be running locally. If our page is served from
// one of these, use relative paths (API_BASE = '').  Any other port means
// we're on a static dev server (Five Server / Live Server) and must point
// to the FastAPI instance explicitly.
const _SERVER_PORTS = ['', '80', '443', '8000', '8081'];
const IS_DEV = !_SERVER_PORTS.includes(location.port);
const API_BASE = IS_DEV ? 'http://127.0.0.1:8000' : '';
const GAME_URL = API_BASE + '/jogo';
// Demo entry URL — appends mode=demo so the game boots into the register flow
const DEMO_URL = GAME_URL + '?mode=demo';

// Fix all /jogo links to use the correct base.
// .btn-demo-free links get the demo URL (mode=demo) so the game opens the register screen.
// Script is loaded at end-of-body so DOM is already available — run immediately.
function _fixGameLinks() {
    document.querySelectorAll('a[href="/jogo"], a[href$="/jogo"]').forEach(a => {
        if (a.classList.contains('btn-demo-free')) {
            a.href = DEMO_URL;
        } else {
            a.href = GAME_URL;
        }
    });
    // Also fix any links that already have ?mode=demo
    document.querySelectorAll('a[href$="/jogo?mode=demo"]').forEach(a => {
        a.href = DEMO_URL;
    });
}
// Run now (DOM ready) AND after DOMContentLoaded as safety net
_fixGameLinks();
document.addEventListener('DOMContentLoaded', _fixGameLinks);

// ── ANALYTICS TRACKER ──────────────────────────────────────────
// Relative URL — works both on Live Server (dev) and when served by FastAPI (prod)
const ANALYTICS_API = API_BASE + '/api/analytics/landing';

(function initTracker() {
    // Persistent anonymous visitor ID per browser
    let vid = localStorage.getItem('_g404_vid');
    if (!vid) {
        vid = 'v-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
        localStorage.setItem('_g404_vid', vid);
    }

    function send(payload) {
        const body = Object.assign({ visitor_id: vid, referrer: document.referrer.slice(0, 500), user_agent: navigator.userAgent.slice(0, 200) }, payload);
        // Use sendBeacon when available (non-blocking, survives page close)
        const data = JSON.stringify(body);
        if (navigator.sendBeacon) {
            const blob = new Blob([data], { type: 'application/json' });
            navigator.sendBeacon(ANALYTICS_API, blob);
        } else {
            fetch(ANALYTICS_API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: data, keepalive: true }).catch(() => { });
        }
    }

    // 1. Page view — fired on load
    send({ event_type: 'page_view' });

    // 2. Button / link clicks via event delegation
    document.addEventListener('click', function (e) {
        const el = e.target.closest('button, a, [data-track]');
        if (!el) return;
        const label = el.id || el.dataset.track || el.getAttribute('data-plan') || el.textContent.trim().slice(0, 60);
        send({ event_type: 'click', element: label });
    }, { passive: true });

    // 3. Section view via IntersectionObserver
    const _observed = new Set();
    if ('IntersectionObserver' in window) {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !_observed.has(entry.target.id)) {
                    _observed.add(entry.target.id);
                    send({ event_type: 'section_view', section: entry.target.id });
                }
            });
        }, { threshold: 0.3 });
        document.querySelectorAll('section[id]').forEach(s => obs.observe(s));
    }

    // 4. Scroll depth milestones
    const _depths = new Set();
    window.addEventListener('scroll', function () {
        const pct = Math.round((window.scrollY + window.innerHeight) / document.body.scrollHeight * 100);
        [25, 50, 75, 100].forEach(milestone => {
            if (pct >= milestone && !_depths.has(milestone)) {
                _depths.add(milestone);
                send({ event_type: 'scroll_depth', scroll_pct: milestone });
            }
        });
    }, { passive: true });
})();

// Expose helper for checkout click tracking
function trackCheckout(plan) {
    const vid = localStorage.getItem('_g404_vid') || 'unknown';
    const body = JSON.stringify({
        visitor_id: vid,
        event_type: 'checkout_click',
        element: 'btn-plan-' + plan,
        plan: plan === 'mensal' ? 'monthly' : 'annual',
        referrer: document.referrer.slice(0, 200),
        user_agent: navigator.userAgent.slice(0, 200),
    });
    if (navigator.sendBeacon) {
        navigator.sendBeacon(ANALYTICS_API, new Blob([body], { type: 'application/json' }));
    } else {
        fetch(ANALYTICS_API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => { });
    }
}

// ── TERMINAL TYPEWRITER ──────────────────────────────────────
const lines = [
    "./start-journey.sh --player=you --level=estagiario",
    "Conectando ao Xerox PARC... 1973 ✓",
    "Alan Kay: 'Welcome, engineer. Let's build the future.'",
    "Java challenge detectado: HelloWorld.java",
    "Compilando... OK  |  Executando... OK",
    "> Nível desbloqueado: Júnior Engineer",
    "Próximo destino: Apple Garage (1976)...",
];

let lineIdx = 0;
let charIdx = 0;
let deleting = false;
let pauseTicks = 0;
const PAUSE_AFTER = 60;
const PAUSE_BEFORE = 20;
const TYPE_SPEED = 38;
const DELETE_SPEED = 14;

function typeWriter() {
    const el = document.getElementById('typedText');
    if (!el) return;

    const current = lines[lineIdx];

    if (!deleting) {
        el.textContent = current.slice(0, charIdx + 1);
        charIdx++;
        if (charIdx === current.length) {
            deleting = true;
            pauseTicks = PAUSE_AFTER;
            setTimeout(typeWriter, pauseTicks * TYPE_SPEED);
            return;
        }
        setTimeout(typeWriter, TYPE_SPEED);
    } else {
        if (pauseTicks > 0) {
            pauseTicks--;
            setTimeout(typeWriter, TYPE_SPEED);
            return;
        }
        el.textContent = current.slice(0, charIdx - 1);
        charIdx--;
        if (charIdx === 0) {
            deleting = false;
            pauseTicks = PAUSE_BEFORE;
            lineIdx = (lineIdx + 1) % lines.length;
            setTimeout(typeWriter, pauseTicks * TYPE_SPEED);
            return;
        }
        setTimeout(typeWriter, DELETE_SPEED);
    }
}
typeWriter();

// ── NAVBAR SCROLL EFFECT ─────────────────────────────────────
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
    if (window.scrollY > 40) {
        navbar.style.borderBottomColor = 'rgba(255,179,71,0.2)';
    } else {
        navbar.style.borderBottomColor = 'rgba(255,255,255,0.07)';
    }
});

// ── HAMBURGER MENU ───────────────────────────────────────────
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobileMenu');

hamburger?.addEventListener('click', () => {
    mobileMenu.classList.toggle('open');
});

// Close mobile menu when a link is clicked
mobileMenu?.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => mobileMenu.classList.remove('open'));
});

// ── FAQ ACCORDION ─────────────────────────────────────────────
function toggleFaq(btn) {
    const answer = btn.nextElementSibling;
    const isOpen = answer.classList.contains('open');

    // Close all
    document.querySelectorAll('.faq-answer.open').forEach(a => a.classList.remove('open'));
    document.querySelectorAll('.faq-question.open').forEach(b => b.classList.remove('open'));

    // Open clicked (if it wasn't open)
    if (!isOpen) {
        answer.classList.add('open');
        btn.classList.add('open');
    }
}

// ── SCROLL REVEAL ─────────────────────────────────────────────
const revealElements = document.querySelectorAll(
    '.timeline-card, .skill-card, .char-card, .plan-card, .faq-item, .step'
);

revealElements.forEach(el => el.classList.add('reveal'));

const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
            setTimeout(() => {
                entry.target.classList.add('visible');
            }, i * 60);
            revealObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

revealElements.forEach(el => revealObserver.observe(el));

// ── SMOOTH SCROLL (Safari fallback) ──────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            const offset = 72; // navbar height
            const top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top, behavior: 'smooth' });
        }
    });
});

// ── CHECKOUT LINKS (Asaas production links — R$5 test products for E2E validation) ──
// NOTE: after E2E validation, swap for real R$97/R$997 product links.
const CHECKOUT_LINKS = {
    mensal: 'https://www.asaas.com/c/k8xqrulte259faq2',
    anual: 'https://www.asaas.com/c/wcc6pckxm4xusbcr',
};

// ── PLAN CLICK HANDLER ───────────────────────────────────────
function handlePlanClick(plan) {
    trackCheckout(plan);

    const token = localStorage.getItem('garage_token');
    const userRaw = localStorage.getItem('garage_user');

    if (!token || !userRaw) {
        // Não está logado — pedir que crie conta primeiro
        _showNeedAccountModal(plan);
        return;
    }

    // Está logado — redirecionar para checkout Asaas
    const link = CHECKOUT_LINKS[plan] || CHECKOUT_LINKS.mensal;
    window.open(link, '_blank', 'noopener');
}

// ── MODAL: usuário sem conta ──────────────────────────────────
function _showNeedAccountModal(plan) {
    const label = plan === 'mensal' ? 'Mensal · R$ 97/mês' : 'Anual · R$ 997/ano';
    _removeModal('_garage_modal');
    const el = document.createElement('div');
    el.id = '_garage_modal';
    el.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px)';
    el.innerHTML = `
      <div style="background:#111118;border:1px solid rgba(255,179,71,0.4);border-radius:20px;padding:40px 32px;max-width:420px;width:100%;text-align:center;font-family:'Inter',sans-serif">
        <div style="font-size:2.4rem;margin-bottom:12px">🔑</div>
        <h3 style="color:#ffb347;font-size:1.25rem;margin-bottom:10px">Crie sua conta gratuita</h3>
        <p style="color:#8888aa;font-size:0.9rem;line-height:1.6;margin-bottom:8px">
          Para assinar o plano <strong style="color:#e8e8f0">${label}</strong>, você precisa de uma conta no 404 Garage.
        </p>
        <p style="color:#8888aa;font-size:0.85rem;margin-bottom:28px">
          O cadastro é gratuito e o <strong style="color:#22c55e">Ato I completo</strong> é de graça.
        </p>
        <a href="${DEMO_URL}" style="display:block;background:#22c55e;color:#0a0a0f;padding:13px 24px;border-radius:10px;font-weight:700;font-size:1rem;text-decoration:none;margin-bottom:12px">
          ▶ Criar conta e jogar grátis
        </a>
        <p style="color:#555570;font-size:0.82rem;margin-bottom:0">
          Já tem conta? <a href="${GAME_URL}" style="color:#ffb347;text-decoration:none">Entrar no jogo</a> e depois volte aqui para assinar.
        </p>
        <button onclick="_removeModal('_garage_modal')" style="background:none;border:none;color:#555570;font-size:0.85rem;margin-top:18px;cursor:pointer">Fechar ×</button>
      </div>`;
    document.body.appendChild(el);
    el.addEventListener('click', e => { if (e.target === el) _removeModal('_garage_modal'); });
}

// ── PIX CHECKOUT ──────────────────────────────────────────────
function _startPixCheckout(plan, token, user) {
    const planLabel = plan === 'mensal' ? 'Mensal · R$ 97/mês' : 'Anual · R$ 997/ano';
    _showPixLoading(planLabel);

    fetch(API_BASE + '/api/payments/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({
            user_id: user.id || user.user_id || '',
            user_name: user.full_name || user.username || 'Assinante',
            user_email: user.email || '',
            plan: plan === 'mensal' ? 'monthly' : 'annual',
        })
    })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (!ok) throw new Error(d.detail || 'Erro ao gerar cobrança');
            _showPixModal(planLabel, d);
        })
        .catch(err => {
            _removeModal('_garage_modal');
            alert('❌ Erro ao iniciar pagamento: ' + err.message + '\n\nTente novamente ou entre em contato.');
        });
}

function _showPixLoading(planLabel) {
    _removeModal('_garage_modal');
    const el = document.createElement('div');
    el.id = '_garage_modal';
    el.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px)';
    el.innerHTML = `
      <div style="background:#111118;border:1px solid rgba(255,179,71,0.3);border-radius:20px;padding:48px 32px;max-width:380px;width:100%;text-align:center;font-family:'Inter',sans-serif">
        <div style="font-size:2rem;margin-bottom:16px">⏳</div>
        <h3 style="color:#ffb347;font-size:1.15rem;margin-bottom:8px">Gerando PIX…</h3>
        <p style="color:#8888aa;font-size:0.9rem">Preparando cobrança para o plano <strong style="color:#e8e8f0">${planLabel}</strong></p>
      </div>`;
    document.body.appendChild(el);
}

function _showPixModal(planLabel, data) {
    _removeModal('_garage_modal');
    const paymentId = data.payment_id;
    const qrBase64 = data.qr_code_base64;
    const copyPaste = data.pix_copy_paste;
    const value = (data.value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const expiresAt = data.expires_at ? new Date(data.expires_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '';

    const el = document.createElement('div');
    el.id = '_garage_modal';
    el.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px);overflow-y:auto';
    el.innerHTML = `
      <div style="background:#111118;border:1px solid rgba(34,197,94,0.4);border-radius:20px;padding:36px 28px;max-width:440px;width:100%;text-align:center;font-family:'Inter',sans-serif">
        <div style="font-size:2rem;margin-bottom:8px">💳</div>
        <h3 style="color:#22c55e;font-size:1.2rem;margin-bottom:4px">Pague via PIX</h3>
        <p style="color:#8888aa;font-size:0.88rem;margin-bottom:20px">Plano: <strong style="color:#e8e8f0">${planLabel}</strong> &nbsp;•&nbsp; <strong style="color:#22c55e">${value}</strong></p>

        ${qrBase64 ? `<img src="data:image/png;base64,${qrBase64}" alt="QR Code PIX" style="width:200px;height:200px;border-radius:12px;background:#fff;padding:8px;margin-bottom:16px">` : ''}

        <p style="color:#8888aa;font-size:0.82rem;margin-bottom:8px">Ou copie a chave PIX:</p>
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <input id="_pix_key" value="${copyPaste || ''}" readonly
            style="flex:1;background:#0d0d15;border:1px solid rgba(255,255,255,0.1);color:#e8e8f0;border-radius:8px;padding:10px 12px;font-size:0.82rem;font-family:monospace;outline:none">
          <button onclick="_copyPix()" id="_copy_btn"
            style="background:#22c55e;color:#0a0a0f;border:none;border-radius:8px;padding:10px 16px;font-weight:700;font-size:0.85rem;cursor:pointer;white-space:nowrap">
            Copiar
          </button>
        </div>

        ${expiresAt ? `<p style="color:#555570;font-size:0.8rem;margin-bottom:16px">⏰ Expira às ${expiresAt}</p>` : ''}

        <div id="_pix_status" style="padding:12px;border-radius:10px;background:rgba(255,179,71,0.08);border:1px solid rgba(255,179,71,0.2);font-size:0.88rem;color:#ffb347;margin-bottom:16px">
          ⏳ Aguardando pagamento…
        </div>

        <button onclick="_removeModal('_garage_modal')" style="background:none;border:none;color:#555570;font-size:0.85rem;cursor:pointer">Cancelar ×</button>
      </div>`;
    document.body.appendChild(el);

    _pollPixStatus(paymentId);
}

function _copyPix() {
    const input = document.getElementById('_pix_key');
    const btn = document.getElementById('_copy_btn');
    if (!input) return;
    navigator.clipboard?.writeText(input.value).catch(() => {
        input.select();
        document.execCommand('copy');
    });
    if (btn) { btn.textContent = 'Copiado ✓'; setTimeout(() => { if (btn) btn.textContent = 'Copiar'; }, 2000); }
}

let _pollTimer = null;
function _pollPixStatus(paymentId) {
    clearTimeout(_pollTimer);
    if (!paymentId || !document.getElementById('_garage_modal')) return;

    fetch(API_BASE + '/api/payments/status/' + paymentId)
        .then(r => r.json())
        .then(data => {
            const status = (data.status || '').toUpperCase();
            const box = document.getElementById('_pix_status');
            if (!box) return;

            if (status === 'CONFIRMED' || status === 'RECEIVED') {
                box.style.background = 'rgba(34,197,94,0.12)';
                box.style.borderColor = 'rgba(34,197,94,0.4)';
                box.style.color = '#22c55e';
                box.innerHTML = '✅ Pagamento confirmado! Redirecionando para o jogo…';
                clearTimeout(_pollTimer);
                setTimeout(() => { window.location.href = GAME_URL; }, 2000);
            } else if (status === 'OVERDUE' || status === 'CANCELLED') {
                box.style.color = '#ef4444';
                box.innerHTML = '❌ Pagamento expirado ou cancelado.';
            } else {
                _pollTimer = setTimeout(() => _pollPixStatus(paymentId), 5000);
            }
        })
        .catch(() => { _pollTimer = setTimeout(() => _pollPixStatus(paymentId), 8000); });
}

function _removeModal(id) {
    clearTimeout(_pollTimer);
    document.getElementById(id)?.remove();
}

// ── ACTIVE NAV LINK ON SCROLL ────────────────────────────────
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-links a');

window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(section => {
        const top = section.offsetTop - 100;
        if (window.scrollY >= top) current = section.getAttribute('id');
    });
    navLinks.forEach(link => {
        link.style.color = link.getAttribute('href') === `#${current}` ? '#ffb347' : '';
    });
}, { passive: true });

// ── CONSOLE ASCII ART ─────────────────────────────────────────
console.log(`%c
 ___  ___  __ _     ____
| | |/ _ \\| | |   / ___|  __ _ _ __ __ _  __ _  ___
| . | | | | . |  | |  _ / _\` | '__/ _\` |/ _\` |/ _ \\
|_|_|\\___/|_|_|  |_|__|| (_| | | | (_| | (_| |  __/
                  \\____| \\__,_|_|  \\__,_|\\__, |\\___|
                                          |___/
  Bio Code Technology Ltda — cezicolatecnologia@gmail.com
  De Estagiário a Principal Engineer 🚀
`, 'color: #ffb347; font-family: monospace; font-size: 11px;');
