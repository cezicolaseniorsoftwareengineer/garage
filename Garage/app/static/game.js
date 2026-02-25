// GARAGE -- 2D platformer engine (Canvas)

// ---- api client (JWT-aware) ----
const API = {
    _headers() {
        const h = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined' && Auth.getToken()) {
            h['Authorization'] = 'Bearer ' + Auth.getToken();
        }
        return h;
    },
    async _handle401(p) {
        if (p.includes('/auth/')) return false;
        const refreshed = await Auth.tryRefresh();
        if (refreshed) return true;
        Auth.handleExpired();
        UI.showScreen('screen-login');
        throw new Error('Sessao expirada. Faca login novamente.');
    },
    async get(p) {
        let r = await fetch(p, { headers: this._headers() });
        if (r.status === 401) { if (await this._handle401(p)) r = await fetch(p, { headers: this._headers() }); }
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
        return r.json();
    },
    async post(p, b) {
        let r = await fetch(p, { method: 'POST', headers: this._headers(), body: JSON.stringify(b) });
        if (r.status === 401) { if (await this._handle401(p)) r = await fetch(p, { method: 'POST', headers: this._headers(), body: JSON.stringify(b) }); }
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
        return r.json();
    },
};

// ---- world state persistence ----
const WorldStatePersistence = {
    _saveTimeout: null,
    _lastSavedState: null,
    _saveIntervalId: null,

    /**
     * Save world state to the backend.
     * Called when books are collected, regions completed, or periodically for position.
     */
    async save(immediate = false) {
        if (!State.sessionId) return;

        const currentState = {
            collected_books: [...State.collectedBooks],
            completed_regions: [...State.completedRegions],
            current_region: State.lockedRegion,
            player_world_x: World.player ? Math.round(World.player.x) : 100,
        };

        // Skip if state hasn't changed (to reduce API calls)
        const stateStr = JSON.stringify(currentState);
        if (this._lastSavedState === stateStr && !immediate) return;

        // Debounce saves unless immediate is requested
        if (!immediate) {
            if (this._saveTimeout) clearTimeout(this._saveTimeout);
            this._saveTimeout = setTimeout(() => this._doSave(currentState, stateStr), 1000);
            return;
        }

        await this._doSave(currentState, stateStr);
    },

    async _doSave(currentState, stateStr) {
        try {
            await API.post('/api/save-world-state', {
                session_id: State.sessionId,
                ...currentState,
            });
            this._lastSavedState = stateStr;
            console.log('[WorldStatePersistence] State saved:', currentState);
        } catch (e) {
            console.error('[WorldStatePersistence] Failed to save state:', e);
        }
    },

    /**
     * Restore world state from the player data received from the server.
     */
    restore(playerData) {
        if (!playerData) return;

        // Restore collected books
        if (Array.isArray(playerData.collected_books)) {
            State.collectedBooks = [...playerData.collected_books];
        }

        // Restore completed regions
        if (Array.isArray(playerData.completed_regions)) {
            State.completedRegions = [...playerData.completed_regions];
        }

        // Restore current region (if player was inside a company)
        if (playerData.current_region) {
            State.lockedRegion = playerData.current_region;
            // Find the NPC and building for the locked region
            const npc = NPC_DATA.find(n => n.region === playerData.current_region);
            if (npc) {
                State.lockedNpc = npc;
                const building = BUILDINGS.find(b => b.name === playerData.current_region);
                if (building) {
                    State.doorAnimBuilding = building;
                }
            }
        }

        // Set the last saved state to prevent immediate re-save
        this._lastSavedState = JSON.stringify({
            collected_books: State.collectedBooks,
            completed_regions: State.completedRegions,
            current_region: State.lockedRegion,
            player_world_x: playerData.player_world_x || 100,
        });

        console.log('[WorldStatePersistence] State restored:', {
            books: State.collectedBooks.length,
            regions: State.completedRegions.length,
            currentRegion: State.lockedRegion,
            worldX: playerData.player_world_x,
        });
    },

    /**
     * Start periodic saves to persist player position.
     */
    startPeriodicSave(intervalMs = 30000) {
        this.stopPeriodicSave();
        this._saveIntervalId = setInterval(() => {
            if (State.sessionId && !State.paused) {
                this.save(false);
            }
        }, intervalMs);
    },

    stopPeriodicSave() {
        if (this._saveIntervalId) {
            clearInterval(this._saveIntervalId);
            this._saveIntervalId = null;
        }
    },

    /**
     * Reset state tracking (used when starting a new game).
     */
    reset() {
        this._lastSavedState = null;
        if (this._saveTimeout) {
            clearTimeout(this._saveTimeout);
            this._saveTimeout = null;
        }
    },
};

// ---- heartbeat for real-time online tracking ----
const Heartbeat = {
    _intervalId: null,
    _intervalMs: 30000, // 30 seconds

    /**
     * Start sending heartbeat pings to mark player as online.
     */
    start() {
        this.stop(); // Ensure no duplicate intervals
        console.log('[Heartbeat] Starting online tracking...');

        // Send immediate ping
        this._sendPing();

        // Start periodic pings
        this._intervalId = setInterval(() => {
            this._sendPing();
        }, this._intervalMs);
    },

    /**
     * Stop sending heartbeat pings.
     */
    stop() {
        if (this._intervalId) {
            clearInterval(this._intervalId);
            this._intervalId = null;
            console.log('[Heartbeat] Stopped online tracking.');
        }
    },

    /**
     * Send a heartbeat ping to the server.
     */
    async _sendPing() {
        if (!State.sessionId) return;

        try {
            await API.post('/api/heartbeat', {
                session_id: State.sessionId,
            });
            console.log('[Heartbeat] Ping sent successfully.');
        } catch (e) {
            console.warn('[Heartbeat] Failed to send ping:', e.message);
        }
    },
};

// ---- study chat (authenticated) ----
const StudyChat = {
    _open: false,
    _busy: false,
    _messages: [],
    _sessionKey: null,
    _bound: false,

    _els() {
        return {
            overlay: document.getElementById('studyChatOverlay'),
            context: document.getElementById('studyChatContext'),
            messages: document.getElementById('studyChatMessages'),
            input: document.getElementById('studyChatInput'),
            send: document.getElementById('studyChatSendBtn'),
        };
    },

    _ensureMounted() {
        // Fallback for stale cached HTML: mount chat UI dynamically inside IDE.
        const ideMain = document.querySelector('.ide-main');
        if (ideMain && !document.getElementById('studyChatOverlay')) {
            const aside = document.createElement('aside');
            aside.id = 'studyChatOverlay';
            aside.className = 'study-chat-overlay';
            aside.innerHTML =
                '<div class="study-chat-card">' +
                '  <div class="study-chat-header">' +
                '    <div><h3>INTELIGÊNCIA ARTIFICIAL</h3><p id="studyChatContext">Java + Estruturas de Dados</p></div>' +
                '    <button class="study-chat-close" onclick="StudyChat.close()">&times;</button>' +
                '  </div>' +
                '  <div id="studyChatMessages" class="study-chat-messages"></div>' +
                '  <div class="study-chat-composer">' +
                '    <textarea id="studyChatInput" placeholder="Pergunte sobre livros, sintaxe Java, algoritmos e escalabilidade..."></textarea>' +
                '    <div class="study-chat-actions"><button id="studyChatSendBtn" class="btn-primary" onclick="StudyChat.send()">ENVIAR</button></div>' +
                '  </div>' +
                '</div>';
            ideMain.appendChild(aside);
        }

        const actions = document.querySelector('.ide-actions');
        if (actions && !document.getElementById('ideChatBtn')) {
            const btn = document.createElement('button');
            btn.className = 'ide-btn ide-btn-chat';
            btn.id = 'ideChatBtn';
            btn.onclick = () => StudyChat.toggle();
            btn.innerHTML = '<span class="ide-btn-icon">&#128172;</span> INTELIGÊNCIA ARTIFICIAL';
            const skipBtn = document.getElementById('ideSkipBtn');
            if (skipBtn && skipBtn.parentElement === actions) {
                actions.insertBefore(btn, skipBtn);
            } else {
                actions.appendChild(btn);
            }
        }
    },

    _storageKey() {
        return 'garage_study_chat_v2_' + (State.sessionId || 'anon');
    },

    _bind() {
        if (this._bound) return;
        const { input } = this._els();
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    StudyChat.send();
                }
            });
        }
        this._bound = true;
    },

    _load() {
        let parsed = [];
        try {
            const raw = localStorage.getItem(this._storageKey());
            parsed = raw ? JSON.parse(raw) : [];
        } catch (_e) {
            parsed = [];
        }
        if (!Array.isArray(parsed)) parsed = [];
        this._messages = parsed
            .filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
            .slice(-20);
    },

    _persist() {
        try {
            localStorage.setItem(this._storageKey(), JSON.stringify(this._messages.slice(-20)));
        } catch (_e) {
            // ignore storage failures
        }
    },

    _ensureSessionState() {
        const key = this._storageKey();
        if (this._sessionKey !== key) {
            this._sessionKey = key;
            this._load();
        }
    },

    _isIdeVisible() {
        const ideOverlay = document.getElementById('ideOverlay');
        return !!(ideOverlay && ideOverlay.classList.contains('visible'));
    },

    isOpen() {
        return this._open;
    },

    _currentRegion() {
        if (IDE && IDE._currentChallenge && IDE._currentChallenge.region) return IDE._currentChallenge.region;
        if (State.lockedRegion) return State.lockedRegion;
        if (State.currentChallenge && State.currentChallenge.region) return State.currentChallenge.region;
        return 'Garage';
    },

    _currentStage() {
        return State.player && State.player.stage ? State.player.stage : 'Intern';
    },

    _bookPayload() {
        if (typeof BOOKS_DATA === 'undefined' || !Array.isArray(BOOKS_DATA)) return [];
        const collected = new Set(State.collectedBooks || []);
        return BOOKS_DATA.map(b => ({
            id: b.id,
            title: b.title,
            author: b.author || '',
            summary: b.summary || '',
            lesson: b.lesson || '',
            collected: collected.has(b.id),
        }));
    },

    _recentPayload() {
        return this._messages.slice(-8).map(m => ({
            role: m.role,
            content: m.content,
        }));
    },

    _append(role, content, meta) {
        this._messages.push({
            role,
            content: content || '',
            meta: meta || '',
            ts: Date.now(),
        });
        this._messages = this._messages.slice(-20);
        this._persist();
        this._render();
    },

    _setBusy(busy) {
        this._busy = busy;
        const { send, input } = this._els();
        if (send) {
            send.disabled = busy;
            send.textContent = busy ? 'ENVIANDO...' : 'ENVIAR';
        }
        if (input) input.disabled = busy;
    },

    _renderMarkdown(text) {
        if (!text) return '';
        // Escape HTML entities first to avoid XSS
        const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Fenced code blocks: ```lang\ncode\n```
        text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
            const langLabel = lang ? `<span class="study-code-lang">${esc(lang)}</span>` : '';
            return `<pre class="study-code-block">${langLabel}<code>${esc(code.trimEnd())}</code></pre>`;
        });
        // Inline code: `code`
        text = text.replace(/`([^`\n]+)`/g, (_m, code) => `<code class="study-inline-code">${esc(code)}</code>`);
        // Bold: **text**
        text = text.replace(/\*\*([^*\n]+)\*\*/g, (_m, t) => `<strong>${esc(t)}</strong>`);
        // Italic: *text* or _text_
        text = text.replace(/\*([^*\n]+)\*/g, (_m, t) => `<em>${esc(t)}</em>`);
        text = text.replace(/_([^_\n]+)_/g, (_m, t) => `<em>${esc(t)}</em>`);

        // Process line-by-line for lists and paragraphs
        const lines = text.split('\n');
        const out = [];
        let inUl = false, inOl = false;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const ulMatch = line.match(/^[-*] (.+)/);
            const olMatch = line.match(/^\d+\. (.+)/);
            const hrMatch = /^---+$/.test(line.trim());

            if (ulMatch) {
                if (inOl) { out.push('</ol>'); inOl = false; }
                if (!inUl) { out.push('<ul class="study-list">'); inUl = true; }
                out.push(`<li>${ulMatch[1]}</li>`);
            } else if (olMatch) {
                if (inUl) { out.push('</ul>'); inUl = false; }
                if (!inOl) { out.push('<ol class="study-list">'); inOl = true; }
                out.push(`<li>${olMatch[1]}</li>`);
            } else {
                if (inUl) { out.push('</ul>'); inUl = false; }
                if (inOl) { out.push('</ol>'); inOl = false; }
                if (hrMatch) {
                    out.push('<hr class="study-hr">');
                } else if (line.trim() === '') {
                    out.push('<br>');
                } else if (/^#{1,3} /.test(line)) {
                    const lvl = line.match(/^(#{1,3}) /)[1].length;
                    const heading = line.replace(/^#{1,3} /, '');
                    out.push(`<h${lvl + 2} class="study-heading">${heading}</h${lvl + 2}>`);
                } else {
                    out.push(`<p class="study-p">${line}</p>`);
                }
            }
        }
        if (inUl) out.push('</ul>');
        if (inOl) out.push('</ol>');
        return out.join('\n');
    },

    _render() {
        const { messages } = this._els();
        if (!messages) return;
        messages.innerHTML = '';
        this._messages.forEach((m) => {
            const wrap = document.createElement('div');
            wrap.className = 'study-msg ' + (m.role === 'user' ? 'study-msg-user' : 'study-msg-assistant');

            const meta = document.createElement('span');
            meta.className = 'study-msg-meta';
            meta.textContent = m.role === 'user'
                ? 'VOCE'
                : (m.meta ? ('INTELIGÊNCIA ARTIFICIAL - ' + m.meta) : 'INTELIGÊNCIA ARTIFICIAL');

            const body = document.createElement('div');
            body.className = 'study-msg-body';
            if (m.role === 'assistant') {
                body.innerHTML = this._renderMarkdown(m.content);
            } else {
                body.textContent = m.content;
            }

            wrap.appendChild(meta);
            wrap.appendChild(body);
            messages.appendChild(wrap);
        });
        messages.scrollTop = messages.scrollHeight;
    },

    _updateContextLabel() {
        const { context } = this._els();
        if (!context) return;
        const stage = this._currentStage();
        const region = this._currentRegion();
        context.textContent = 'Stage: ' + stage + ' | Regiao: ' + region;
    },

    _renderLast() {
        // Efficiently update only the last message element during streaming
        const { messages } = this._els();
        if (!messages) return;
        const last = this._messages[this._messages.length - 1];
        if (!last) return;
        const children = messages.children;
        const lastEl = children[children.length - 1];
        if (lastEl) {
            const body = lastEl.querySelector('.study-msg-body');
            if (body) {
                body.innerHTML = this._renderMarkdown(last.content);
                messages.scrollTop = messages.scrollHeight;
                return;
            }
        }
        // Fallback: full render
        this._render();
    },

    open(focusInput = true) {
        if (!Auth.isLoggedIn()) return;
        if (!this._isIdeVisible()) return;
        this._ensureMounted();
        this._bind();
        this._ensureSessionState();

        const { overlay, input } = this._els();
        if (!overlay) return;
        overlay.classList.add('visible');
        this._open = true;
        this._updateContextLabel();
        const btn = document.getElementById('ideChatBtn');
        if (btn) btn.classList.add('active');

        if (this._messages.length === 0) {
            this._append(
                'assistant',
                'Pronto para estudar. Pergunte sobre sintaxe Java, estruturas de dados, algoritmos, trade-offs e como escalar codigo com seguranca.',
                'inicio'
            );
        } else {
            this._render();
        }
        if (focusInput && input) input.focus();
    },

    close() {
        const { overlay } = this._els();
        if (overlay) overlay.classList.remove('visible');
        this._open = false;
        const btn = document.getElementById('ideChatBtn');
        if (btn) btn.classList.remove('active');
        // Return focus to IDE editor when chat is closed during live coding.
        const ideOpen = document.getElementById('ideOverlay') && document.getElementById('ideOverlay').classList.contains('visible');
        if (ideOpen) {
            const ideInput = document.getElementById('ideCodeInput');
            if (ideInput) ideInput.focus();
        }
    },

    toggle() {
        if (this._open) this.close();
        else this.open(true);
    },

    async send() {
        if (this._busy) return;
        if (!State.sessionId) {
            alert('Sessao nao iniciada.');
            return;
        }
        const { input } = this._els();
        if (!input) return;
        const message = (input.value || '').trim();
        if (!message) return;

        const challengeId = IDE && IDE._currentChallenge ? IDE._currentChallenge.id : null;
        const region = this._currentRegion();
        const stage = this._currentStage();

        this._append('user', message);
        input.value = '';
        this._setBusy(true);

        // --- Streaming SSE: text appears token-by-token ---
        const body = JSON.stringify({
            session_id: State.sessionId,
            message,
            challenge_id: challengeId,
            region,
            stage,
            recent_messages: this._recentPayload(),
            books: this._bookPayload(),
        });

        // Insert placeholder bubble with typing cursor immediately
        this._messages.push({ role: 'assistant', content: '▌', meta: '', ts: Date.now() });
        this._messages = this._messages.slice(-20);
        this._render();

        let fullText = '';
        let finalModel = '';
        let streamFailed = false;

        try {
            const resp = await fetch('/api/study/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(Auth.getToken() ? { 'Authorization': 'Bearer ' + Auth.getToken() } : {}),
                },
                body,
            });

            if (!resp.ok) {
                let errMsg = `Erro ${resp.status}`;
                try { const j = await resp.json(); errMsg = j.detail || errMsg; } catch (_e) { }
                if (resp.status === 429 || errMsg.toLowerCase().includes('limite')) {
                    errMsg = 'Limite de mensagens por minuto atingido. Aguarde um momento.';
                }
                throw new Error(errMsg);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buf = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                const lines = buf.split('\n');
                buf = lines.pop(); // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const raw = line.slice(6).trim();
                    if (!raw || raw === '[DONE]') continue;
                    let parsed;
                    try { parsed = JSON.parse(raw); } catch (_e) { continue; }

                    if (parsed.err) {
                        throw new Error(parsed.err);
                    }
                    if (parsed.d !== undefined) {
                        fullText += parsed.d;
                        // Update last message in-place (avoid full re-render on each token)
                        const last = this._messages[this._messages.length - 1];
                        if (last && last.role === 'assistant') {
                            last.content = fullText + '▌';
                            this._renderLast();
                        }
                    }
                    if (parsed.done) {
                        finalModel = parsed.model || '';
                    }
                }
            }
        } catch (e) {
            streamFailed = true;
            const msg = (e.message || '');
            fullText = msg.includes('429') || msg.toLowerCase().includes('limite')
                ? 'Limite de mensagens por minuto atingido. Aguarde um momento e tente novamente.'
                : 'Falha ao consultar a Inteligência Artificial: ' + (msg || 'erro desconhecido');
            finalModel = 'erro';
        } finally {
            // Finalize last message: remove cursor, persist
            const last = this._messages[this._messages.length - 1];
            if (last && last.role === 'assistant') {
                last.content = fullText || (streamFailed ? fullText : 'Sem resposta.');
                last.meta = finalModel;
                this._persist();
                this._render();
            }
            this._setBusy(false);
            if (input) input.focus();
        }
    },
};

// ---- sound engine (Web Audio, procedural) ----
const SFX = {
    ctx: null,
    _musicNodes: [],
    _musicPlaying: false,
    _musicPaused: false,
    _currentPhase: null,
    masterVol: null,
    musicGain: null,
    musicVol: 0.018,
    musicTargetVol: 0.35,
    sfxVol: 0.18,
    _audioElement: null,

    _getAudio() {
        if (!this._audioElement) {
            this._audioElement = new Audio('/static/music_game.mp3');
            this._audioElement.loop = true;
            this._audioElement.volume = this.musicTargetVol;
        }
        return this._audioElement;
    },

    _init() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterVol = this.ctx.createGain();
            this.masterVol.gain.value = 0.9;
            this.masterVol.connect(this.ctx.destination);
            this.musicGain = this.ctx.createGain();
            this.musicGain.gain.value = 1.0;
            this.musicGain.connect(this.masterVol);
        }
        // Resume context if suspended (required on mobile/Chrome after policy change)
        if (this.ctx.state === 'suspended') this.ctx.resume();
    },

    // Lo-fi filtered tone: sine/triangle through low-pass filter
    _lofiTone(freq, dur, type, vol, cutoff) {
        this._init();
        const o = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        const f = this.ctx.createBiquadFilter();
        o.type = type || 'sine';
        o.frequency.value = freq;
        f.type = 'lowpass';
        f.frequency.value = cutoff || 1200;
        f.Q.value = 1.5;
        g.gain.setValueAtTime(vol || this.sfxVol, this.ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
        o.connect(f); f.connect(g); g.connect(this.masterVol);
        o.start(); o.stop(this.ctx.currentTime + dur);
    },

    _tone(freq, dur, type, vol) {
        this._lofiTone(freq, dur, type || 'triangle', vol || this.sfxVol, 2000);
    },

    _arpeggio(notes, speed, type, vol) {
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, speed * 0.9 / 1000, type || 'sine', vol || 0.12, 1500), i * speed));
    },

    // Warm chord: plays multiple notes as a soft pad
    _chord(freqs, dur, vol, cutoff) {
        this._init();
        const t = this.ctx.currentTime;
        freqs.forEach(freq => {
            if (freq <= 0) return;
            const o = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            const f = this.ctx.createBiquadFilter();
            o.type = 'sine';
            o.frequency.value = freq;
            // Slight detune for warmth
            o.detune.value = (Math.random() - 0.5) * 8;
            f.type = 'lowpass';
            f.frequency.value = cutoff || 800;
            f.Q.value = 0.7;
            const v = vol || 0.012;
            g.gain.setValueAtTime(0.001, t);
            g.gain.linearRampToValueAtTime(v, t + 0.08);
            g.gain.setValueAtTime(v, t + dur * 0.6);
            g.gain.exponentialRampToValueAtTime(0.001, t + dur);
            o.connect(f); f.connect(g); g.connect(this.musicGain);
            o.start(t); o.stop(t + dur + 0.05);
            this._musicNodes.push(o);
        });
    },

    // Lo-fi drum hits (boom-bap percussion)
    _lofiKick(time) {
        this._init();
        const o = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        o.type = 'sine';
        o.frequency.setValueAtTime(150, time);
        o.frequency.exponentialRampToValueAtTime(35, time + 0.08);
        const v = this.musicVol * 2.8;
        g.gain.setValueAtTime(v, time);
        g.gain.exponentialRampToValueAtTime(0.001, time + 0.12);
        o.connect(g); g.connect(this.musicGain);
        o.start(time); o.stop(time + 0.15);
        this._musicNodes.push(o);
    },

    _lofiSnare(time) {
        this._init();
        // Body tone
        const o = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        o.type = 'triangle';
        o.frequency.value = 180;
        const v = this.musicVol * 1.4;
        g.gain.setValueAtTime(v, time);
        g.gain.exponentialRampToValueAtTime(0.001, time + 0.09);
        o.connect(g); g.connect(this.musicGain);
        o.start(time); o.stop(time + 0.12);
        this._musicNodes.push(o);
        // Noise burst
        const bufSize = this.ctx.sampleRate * 0.06;
        const buf = this.ctx.createBuffer(1, bufSize, this.ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = (Math.random() - 0.5) * 0.6;
        const src = this.ctx.createBufferSource();
        src.buffer = buf;
        const ng = this.ctx.createGain();
        const lp = this.ctx.createBiquadFilter();
        lp.type = 'bandpass'; lp.frequency.value = 4000; lp.Q.value = 1.2;
        ng.gain.setValueAtTime(this.musicVol * 1.0, time);
        ng.gain.exponentialRampToValueAtTime(0.001, time + 0.06);
        src.connect(lp); lp.connect(ng); ng.connect(this.musicGain);
        src.start(time); src.stop(time + 0.08);
        this._musicNodes.push(src);
    },

    _lofiHat(time, vol, open) {
        this._init();
        const bufSize = this.ctx.sampleRate * (open ? 0.08 : 0.025);
        const buf = this.ctx.createBuffer(1, bufSize, this.ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = (Math.random() - 0.5) * 0.3;
        const src = this.ctx.createBufferSource();
        src.buffer = buf;
        const g = this.ctx.createGain();
        const hp = this.ctx.createBiquadFilter();
        hp.type = 'highpass'; hp.frequency.value = 7000;
        const v = vol || this.musicVol * 0.5;
        const decay = open ? 0.08 : 0.025;
        g.gain.setValueAtTime(v, time);
        g.gain.exponentialRampToValueAtTime(0.001, time + decay);
        src.connect(hp); hp.connect(g); g.connect(this.musicGain);
        src.start(time); src.stop(time + decay + 0.01);
        this._musicNodes.push(src);
    },

    // Vinyl crackle noise (lo-fi texture)
    _startVinylCrackle() {
        this._init();
        const bufSize = this.ctx.sampleRate * 2;
        const buf = this.ctx.createBuffer(1, bufSize, this.ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) {
            // Sparse crackle: mostly silence with rare pops
            data[i] = Math.random() < 0.002 ? (Math.random() - 0.5) * 0.8 : (Math.random() - 0.5) * 0.01;
        }
        const src = this.ctx.createBufferSource();
        src.buffer = buf;
        src.loop = true;
        const g = this.ctx.createGain();
        g.gain.value = 0.008;
        const f = this.ctx.createBiquadFilter();
        f.type = 'bandpass';
        f.frequency.value = 3000;
        f.Q.value = 0.5;
        src.connect(f); f.connect(g); g.connect(this.musicGain);
        src.start();
        this._musicNodes.push(src);
        this._crackleNode = src;
    },

    // --- SFX (soft, filtered) ---
    jump() {
        this._init();
        const o = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        const f = this.ctx.createBiquadFilter();
        o.type = 'sine';
        o.frequency.setValueAtTime(280, this.ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(560, this.ctx.currentTime + 0.12);
        f.type = 'lowpass'; f.frequency.value = 1500;
        g.gain.setValueAtTime(this.sfxVol, this.ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.15);
        o.connect(f); f.connect(g); g.connect(this.masterVol);
        o.start(); o.stop(this.ctx.currentTime + 0.15);
    },

    land() {
        this._lofiTone(90, 0.05, 'sine', 0.10, 600);
    },

    step() { this._lofiTone(100 + Math.random() * 20, 0.025, 'sine', 0.05, 500); },
    run() { this._lofiTone(140 + Math.random() * 30, 0.02, 'sine', 0.04, 600); },

    talk() {
        const notes = [330, 392, 349, 440, 370];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.035, 'sine', 0.10, 1200), i * 55));
    },

    correct() {
        this._arpeggio([523, 659, 784], 100, 'sine', 0.14);
        setTimeout(() => this._lofiTone(1047, 0.3, 'sine', 0.12, 1500), 350);
    },

    wrong() {
        this._lofiTone(250, 0.15, 'triangle', 0.14, 800);
        setTimeout(() => this._lofiTone(180, 0.2, 'triangle', 0.12, 600), 160);
    },

    promote() {
        const notes = [392, 440, 523, 659, 784];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.25, 'sine', 0.16, 1400), i * 140));
        setTimeout(() => {
            [262, 330, 392].forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.35, 'triangle', 0.10, 800), i * 180));
        }, 80);
    },

    bookCollect() {
        this._init();
        const notes = [659, 784, 988, 1319];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.1, 'sine', 0.14, 1800), i * 60));
        setTimeout(() => this._lofiTone(1568, 0.25, 'sine', 0.12, 1200), 280);
    },

    npcInteract() {
        this._arpeggio([349, 440, 523], 70, 'sine', 0.14);
    },

    gameOver() {
        const notes = [392, 349, 330, 294, 262];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.3, 'triangle', 0.14, 700), i * 200));
    },

    victory() {
        const melody = [523, 659, 784, 1047, 784, 1047, 1319];
        melody.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.2, 'sine', 0.14, 1600), i * 150));
    },

    menuSelect() {
        this._lofiTone(600, 0.05, 'sine', 0.12, 1500);
        setTimeout(() => this._lofiTone(900, 0.06, 'sine', 0.10, 1200), 50);
    },

    menuConfirm() {
        this._arpeggio([440, 659, 880], 55, 'sine', 0.14);
    },

    challengeOpen() {
        this._arpeggio([330, 392, 494, 587], 80, 'sine', 0.12);
    },

    // ---------------------------------------------------------------
    // MUSIC SYSTEM
    // Title/Onboarding = Arcade chiptune (8-bit fliperma)
    // Explore/Challenge = Upbeat Jazz Trio (piano/bass/drums, swing)
    // ---------------------------------------------------------------

    // === ARCADE CHIPTUNE (square wave, bright, energetic) ===
    _arcadeData: {
        bpm: 150,
        // Catchy 8-bit melody (think Mega Man select screen / Contra menu)
        melody: [
            // Phrase A (upbeat intro)
            [659, 1], [784, 1], [880, 2], [784, 1], [659, 1], [587, 1], [523, 1],
            [440, 1], [523, 1], [587, 2], [0, 1], [440, 1], [523, 1], [587, 1],
            // Phrase B (ascending energy)
            [659, 1], [784, 1], [880, 1], [1047, 2], [880, 1], [784, 1], [659, 1],
            [587, 2], [523, 1], [440, 1], [523, 2], [0, 2],
            // Phrase C (hook)
            [880, 1], [0, 1], [880, 1], [784, 1], [659, 2], [784, 1], [880, 1],
            [1047, 2], [0, 1], [880, 1], [784, 1], [659, 2], [0, 2],
        ],
        bass: [
            [165, 2], [165, 2], [196, 2], [196, 2],
            [220, 2], [220, 2], [196, 2], [165, 2],
            [131, 2], [131, 2], [165, 2], [165, 2],
            [196, 2], [196, 2], [220, 2], [165, 2],
            [220, 2], [220, 2], [196, 2], [196, 2],
            [165, 2], [165, 2], [131, 2], [131, 2],
        ],
        // Counter-melody (harmony layer)
        harmony: [
            [330, 2], [392, 2], [440, 2], [392, 2],
            [330, 2], [294, 2], [330, 4],
            [392, 2], [440, 2], [523, 2], [440, 2],
            [392, 4], [330, 4],
            [440, 2], [440, 2], [392, 2], [330, 2],
            [523, 4], [440, 2], [392, 2],
        ],
    },

    _playArcade() {
        this._init();
        const data = this._arcadeData;
        const beatSec = 60 / data.bpm;
        const totalMelBeats = data.melody.reduce((s, n) => s + n[1], 0);
        const loopDur = totalMelBeats * beatSec;

        const playLoop = () => {
            if (!this._musicPlaying || this._currentPhase !== 'title') return;
            // Prune dead nodes from previous loop iteration to prevent memory leak
            this._musicNodes = [];
            const now = this.ctx.currentTime + 0.05;

            // --- Lead melody (bright square wave) ---
            let t = now;
            data.melody.forEach(([freq, beats]) => {
                const dur = beats * beatSec;
                if (freq > 0) {
                    const o = this.ctx.createOscillator();
                    const g = this.ctx.createGain();
                    o.type = 'square';
                    o.frequency.value = freq;
                    const v = this.musicVol * 1.6;
                    g.gain.setValueAtTime(v, t);
                    g.gain.setValueAtTime(v * 0.7, t + dur * 0.75);
                    g.gain.exponentialRampToValueAtTime(0.001, t + dur * 0.95);
                    o.connect(g); g.connect(this.musicGain);
                    o.start(t); o.stop(t + dur);
                    this._musicNodes.push(o);
                }
                t += dur;
            });

            // --- Harmony (triangle, softer) ---
            let th = now;
            data.harmony.forEach(([freq, beats]) => {
                const dur = beats * beatSec;
                if (freq > 0) {
                    const o = this.ctx.createOscillator();
                    const g = this.ctx.createGain();
                    o.type = 'triangle';
                    o.frequency.value = freq;
                    const v = this.musicVol * 0.7;
                    g.gain.setValueAtTime(v, th);
                    g.gain.exponentialRampToValueAtTime(0.001, th + dur * 0.9);
                    o.connect(g); g.connect(this.musicGain);
                    o.start(th); o.stop(th + dur);
                    this._musicNodes.push(o);
                }
                th += dur;
            });

            // --- Bass (triangle, punchy) ---
            let tb = now;
            data.bass.forEach(([freq, beats]) => {
                const dur = beats * beatSec;
                if (freq > 0) {
                    const o = this.ctx.createOscillator();
                    const g = this.ctx.createGain();
                    o.type = 'triangle';
                    o.frequency.value = freq;
                    const v = this.musicVol * 1.2;
                    g.gain.setValueAtTime(v, tb);
                    g.gain.exponentialRampToValueAtTime(0.001, tb + dur * 0.85);
                    o.connect(g); g.connect(this.musicGain);
                    o.start(tb); o.stop(tb + dur);
                    this._musicNodes.push(o);
                }
                tb += dur;
            });

            // --- Drums (tight NES-style) ---
            for (let b = 0; b < totalMelBeats; b++) {
                const bt = now + b * beatSec;

                // Hi-hat every beat (short noise burst)
                const hh = this.ctx.createOscillator();
                const hg = this.ctx.createGain();
                hh.type = 'square';
                hh.frequency.value = 5500 + Math.random() * 3000;
                hg.gain.setValueAtTime(this.musicVol * 0.25, bt);
                hg.gain.exponentialRampToValueAtTime(0.001, bt + 0.025);
                hh.connect(hg); hg.connect(this.musicGain);
                hh.start(bt); hh.stop(bt + 0.03);
                this._musicNodes.push(hh);

                // Kick on 0, 4, 8... (every 4 beats)
                if (b % 4 === 0) {
                    const k = this.ctx.createOscillator();
                    const kg = this.ctx.createGain();
                    k.type = 'sine';
                    k.frequency.setValueAtTime(180, bt);
                    k.frequency.exponentialRampToValueAtTime(40, bt + 0.06);
                    kg.gain.setValueAtTime(this.musicVol * 2.5, bt);
                    kg.gain.exponentialRampToValueAtTime(0.001, bt + 0.1);
                    k.connect(kg); kg.connect(this.musicGain);
                    k.start(bt); k.stop(bt + 0.12);
                    this._musicNodes.push(k);
                }

                // Snare on 2, 6, 10... (every 4 beats, offset by 2)
                if (b % 4 === 2) {
                    // NES-style snare = short noise + tone
                    const sn = this.ctx.createOscillator();
                    const sg = this.ctx.createGain();
                    sn.type = 'square';
                    sn.frequency.value = 200 + Math.random() * 100;
                    sg.gain.setValueAtTime(this.musicVol * 1.2, bt);
                    sg.gain.exponentialRampToValueAtTime(0.001, bt + 0.08);
                    sn.connect(sg); sg.connect(this.musicGain);
                    sn.start(bt); sn.stop(bt + 0.1);
                    this._musicNodes.push(sn);

                    const sn2 = this.ctx.createOscillator();
                    const sg2 = this.ctx.createGain();
                    sn2.type = 'square';
                    sn2.frequency.value = 4000 + Math.random() * 2000;
                    sg2.gain.setValueAtTime(this.musicVol * 0.6, bt);
                    sg2.gain.exponentialRampToValueAtTime(0.001, bt + 0.05);
                    sn2.connect(sg2); sg2.connect(this.musicGain);
                    sn2.start(bt); sn2.stop(bt + 0.06);
                    this._musicNodes.push(sn2);
                }
            }

            this._musicTimer = setTimeout(() => playLoop(), loopDur * 1000 - 150);
        };

        playLoop();
    },

    // === UPBEAT JAZZ TRIO (swinging, bright, animated -- piano/bass/drums) ===
    _lofiChords: {
        explore: {
            bpm: 152,
            chords: [
                // Cmaj9 -> A7#9 -> Dm9 -> G13 (bright I-VI-ii-V swing)
                { notes: [262, 330, 392, 494, 587], beats: 8 },
                { notes: [220, 277, 330, 440, 523], beats: 8 },
                { notes: [294, 349, 440, 523, 659], beats: 8 },
                { notes: [196, 247, 294, 392, 466], beats: 8 },
                // Fmaj7 -> Bb9 -> Em7 -> A7 (IV-bVII-iii-VI turnaround, cheerful)
                { notes: [175, 262, 330, 415, 523], beats: 8 },
                { notes: [233, 294, 349, 440, 523], beats: 8 },
                { notes: [330, 392, 494, 587, 659], beats: 8 },
                { notes: [220, 277, 330, 440, 554], beats: 8 },
            ],
            melody: [
                // Swinging upbeat melody -- ascending, syncopated, joyful
                [523, 0.5], [587, 0.5], [659, 1], [0, 0.5], [784, 0.5], [880, 1],
                [784, 0.5], [0, 0.5], [659, 1], [698, 0.5], [784, 0.5], [880, 1],
                [0, 0.5], [784, 0.5], [659, 1], [587, 0.5], [659, 0.5], [784, 1],
                [0, 0.5], [880, 0.5], [988, 1], [880, 0.5], [784, 0.5], [0, 1],
                [659, 0.5], [698, 0.5], [784, 1], [880, 1], [0, 0.5], [988, 0.5],
                [1047, 1], [988, 0.5], [0, 0.5], [880, 1], [784, 0.5], [698, 0.5],
                [659, 1], [0, 0.5], [587, 0.5], [523, 1], [587, 0.5], [659, 0.5],
                [784, 1], [0, 0.5], [880, 0.5], [784, 1], [659, 1], [0, 1],
                [587, 0.5], [659, 0.5], [784, 1], [880, 0.5], [0, 0.5], [988, 1],
                [1047, 0.5], [988, 0.5], [880, 1], [784, 0.5], [0, 0.5], [659, 1],
            ],
            bassLine: [
                // Swinging walking bass -- ascending motion, strong beat feel
                [131, 1], [147, 1], [165, 1], [175, 1],
                [196, 1], [185, 1], [175, 1], [165, 1],
                [147, 1], [165, 1], [175, 1], [196, 1],
                [220, 1], [196, 1], [185, 1], [175, 1],
                [165, 1], [175, 1], [196, 1], [220, 1],
                [196, 1], [175, 1], [165, 1], [147, 1],
                [131, 1], [147, 1], [165, 1], [175, 1],
                [196, 1], [220, 1], [196, 1], [175, 1],
                [165, 1], [147, 1], [131, 1], [147, 1],
                [165, 1], [185, 1], [196, 1], [220, 1],
                [247, 1], [220, 1], [196, 1], [175, 1],
                [165, 1], [147, 1], [165, 1], [196, 1],
                [220, 1], [247, 1], [220, 1], [196, 1],
                [175, 1], [165, 1], [147, 1], [131, 1],
                [147, 1], [165, 1], [196, 1], [220, 1],
                [196, 1], [175, 1], [147, 1], [131, 1],
            ],
        },
        challenge: {
            bpm: 160,
            chords: [
                // Fmaj9 -> D9 -> Gm9 -> C13 (bright swing, driving focus)
                { notes: [175, 262, 330, 415, 523], beats: 8 },
                { notes: [294, 370, 440, 523, 659], beats: 8 },
                { notes: [196, 294, 349, 440, 523], beats: 8 },
                { notes: [262, 330, 392, 466, 587], beats: 8 },
                // Bbmaj7 -> Em7 -> A13 -> Dmaj9 (energetic turnaround, triumphant)
                { notes: [233, 294, 349, 440, 587], beats: 8 },
                { notes: [330, 392, 494, 587, 698], beats: 8 },
                { notes: [220, 277, 330, 440, 554], beats: 8 },
                { notes: [294, 370, 440, 554, 659], beats: 8 },
            ],
            melody: [
                // Driving, focused bebop melody -- fast ascending runs, confident
                [698, 0.5], [784, 0.5], [880, 1], [0, 0.5], [988, 0.5], [1047, 1],
                [988, 0.5], [0, 0.5], [880, 1], [784, 0.5], [880, 0.5], [988, 1],
                [0, 0.5], [1047, 0.5], [1175, 1], [1047, 0.5], [988, 0.5], [0, 1],
                [880, 0.5], [784, 0.5], [698, 1], [784, 0.5], [880, 0.5], [988, 1],
                [0, 0.5], [1047, 0.5], [1175, 1], [1319, 0.5], [0, 0.5], [1175, 1],
                [1047, 0.5], [988, 0.5], [880, 1], [0, 0.5], [784, 0.5], [698, 1],
                [784, 0.5], [880, 0.5], [988, 1], [0, 0.5], [1047, 0.5], [1175, 1],
                [1047, 1], [988, 0.5], [880, 0.5], [784, 1], [0, 1], [698, 1],
                [784, 0.5], [880, 0.5], [988, 1], [1047, 0.5], [0, 0.5], [1175, 1],
                [1319, 0.5], [1175, 0.5], [1047, 1], [988, 0.5], [0, 0.5], [880, 1],
            ],
            bassLine: [
                // Driving walking bass -- propulsive, ascending energy
                [175, 1], [196, 1], [220, 1], [233, 1],
                [247, 1], [233, 1], [220, 1], [196, 1],
                [175, 1], [165, 1], [147, 1], [165, 1],
                [175, 1], [196, 1], [220, 1], [247, 1],
                [262, 1], [247, 1], [233, 1], [220, 1],
                [196, 1], [220, 1], [247, 1], [262, 1],
                [294, 1], [262, 1], [247, 1], [220, 1],
                [196, 1], [175, 1], [165, 1], [175, 1],
                [196, 1], [220, 1], [247, 1], [262, 1],
                [294, 1], [262, 1], [247, 1], [233, 1],
                [220, 1], [196, 1], [175, 1], [196, 1],
                [220, 1], [247, 1], [262, 1], [294, 1],
                [262, 1], [247, 1], [220, 1], [196, 1],
                [175, 1], [165, 1], [175, 1], [196, 1],
                [220, 1], [247, 1], [262, 1], [247, 1],
                [220, 1], [196, 1], [175, 1], [165, 1],
            ],
        },
    },

    _playLofi(phase) {
        this._init();
        const data = this._lofiChords[phase];
        if (!data) return;

        const beatSec = 60 / data.bpm;
        const totalBeats = data.chords.reduce((s, c) => s + c.beats, 0);
        const loopDur = totalBeats * beatSec;

        // Subtle room ambience instead of vinyl crackle
        this._startVinylCrackle();

        // --- Piano note synthesizer (acoustic piano timbre) ---
        const pianoNote = (freq, time, dur, vel) => {
            if (freq <= 0) return;
            const v = vel || this.musicVol * 0.9;
            // Fundamental (sine)
            const o1 = this.ctx.createOscillator();
            const g1 = this.ctx.createGain();
            o1.type = 'sine';
            o1.frequency.value = freq;
            o1.detune.value = (Math.random() - 0.5) * 4;
            g1.gain.setValueAtTime(0.001, time);
            g1.gain.linearRampToValueAtTime(v, time + 0.005);
            g1.gain.exponentialRampToValueAtTime(v * 0.45, time + 0.08);
            g1.gain.exponentialRampToValueAtTime(v * 0.18, time + dur * 0.5);
            g1.gain.exponentialRampToValueAtTime(0.001, time + dur * 0.92);
            o1.connect(g1); g1.connect(this.musicGain);
            o1.start(time); o1.stop(time + dur);
            this._musicNodes.push(o1);

            // 2nd harmonic (octave, softer)
            const o2 = this.ctx.createOscillator();
            const g2 = this.ctx.createGain();
            o2.type = 'sine';
            o2.frequency.value = freq * 2;
            g2.gain.setValueAtTime(0.001, time);
            g2.gain.linearRampToValueAtTime(v * 0.3, time + 0.003);
            g2.gain.exponentialRampToValueAtTime(v * 0.08, time + 0.06);
            g2.gain.exponentialRampToValueAtTime(0.001, time + dur * 0.5);
            o2.connect(g2); g2.connect(this.musicGain);
            o2.start(time); o2.stop(time + dur);
            this._musicNodes.push(o2);

            // 3rd harmonic (5th above octave, very soft -- adds brightness)
            const o3 = this.ctx.createOscillator();
            const g3 = this.ctx.createGain();
            o3.type = 'sine';
            o3.frequency.value = freq * 3;
            const lp = this.ctx.createBiquadFilter();
            lp.type = 'lowpass';
            lp.frequency.value = 3800;
            g3.gain.setValueAtTime(0.001, time);
            g3.gain.linearRampToValueAtTime(v * 0.18, time + 0.002);
            g3.gain.exponentialRampToValueAtTime(0.001, time + dur * 0.3);
            o3.connect(lp); lp.connect(g3); g3.connect(this.musicGain);
            o3.start(time); o3.stop(time + dur);
            this._musicNodes.push(o3);

            // Key click (percussive transient -- hammer on string)
            const click = this.ctx.createOscillator();
            const cg = this.ctx.createGain();
            click.type = 'triangle';
            click.frequency.value = freq * 5.3;
            cg.gain.setValueAtTime(v * 0.25, time);
            cg.gain.exponentialRampToValueAtTime(0.001, time + 0.015);
            click.connect(cg); cg.connect(this.musicGain);
            click.start(time); click.stop(time + 0.02);
            this._musicNodes.push(click);
        };

        // --- Jazz brush on ride cymbal ---
        const brushRide = (time, vol) => {
            const v = vol || this.musicVol * 0.25;
            // Filtered noise via detuned high oscillator
            const o = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            const bp = this.ctx.createBiquadFilter();
            o.type = 'triangle';
            o.frequency.value = 6000 + Math.random() * 2000;
            bp.type = 'bandpass';
            bp.frequency.value = 8000;
            bp.Q.value = 0.5;
            g.gain.setValueAtTime(v, time);
            g.gain.exponentialRampToValueAtTime(v * 0.3, time + 0.04);
            g.gain.exponentialRampToValueAtTime(0.001, time + 0.18);
            o.connect(bp); bp.connect(g); g.connect(this.musicGain);
            o.start(time); o.stop(time + 0.2);
            this._musicNodes.push(o);
        };

        // --- Ghost snare (brush swish, very soft) ---
        const ghostSnare = (time, vol) => {
            const v = vol || this.musicVol * 0.15;
            const o = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            o.type = 'triangle';
            o.frequency.value = 180 + Math.random() * 40;
            g.gain.setValueAtTime(v, time);
            g.gain.exponentialRampToValueAtTime(0.001, time + 0.08);
            o.connect(g); g.connect(this.musicGain);
            o.start(time); o.stop(time + 0.1);
            this._musicNodes.push(o);
            // Brush noise layer
            const n = this.ctx.createOscillator();
            const ng = this.ctx.createGain();
            const hp = this.ctx.createBiquadFilter();
            n.type = 'sawtooth';
            n.frequency.value = 3500 + Math.random() * 1500;
            hp.type = 'highpass'; hp.frequency.value = 2500;
            ng.gain.setValueAtTime(v * 0.5, time);
            ng.gain.exponentialRampToValueAtTime(0.001, time + 0.06);
            n.connect(hp); hp.connect(ng); ng.connect(this.musicGain);
            n.start(time); n.stop(time + 0.08);
            this._musicNodes.push(n);
        };

        const playLoop = () => {
            if (!this._musicPlaying || this._currentPhase !== phase) return;
            // Prune dead nodes from previous loop iteration to prevent memory leak
            this._musicNodes = [];
            const now = this.ctx.currentTime + 0.05;
            const swing = 0.12;

            // --- Piano chord voicings (comping with rhythmic variation) ---
            let chordT = now;
            data.chords.forEach(chord => {
                const dur = chord.beats * beatSec;
                const t = chordT;
                // Jazz comping: hit on 1, sometimes on "&" of 2 and 4
                const hits = [0, 2.5, 4, 6.5];
                hits.forEach(beatOff => {
                    if (Math.random() > 0.75 && beatOff > 0) return; // skip some for variation
                    const ht = t + beatOff * beatSec;
                    const chordDur = beatSec * (1.2 + Math.random() * 0.5);
                    chord.notes.forEach((freq, i) => {
                        if (freq <= 0) return;
                        // Skip root occasionally for open voicing
                        if (i === 0 && Math.random() > 0.6) return;
                        const vel = this.musicVol * (0.35 + Math.random() * 0.15);
                        pianoNote(freq, ht, chordDur, vel);
                    });
                });
                chordT += dur;
            });

            // --- Right-hand melody (piano, bebop phrasing) ---
            let melT = now;
            data.melody.forEach(([freq, beats]) => {
                const dur = beats * beatSec;
                if (freq > 0) {
                    const vel = this.musicVol * (0.7 + Math.random() * 0.25);
                    pianoNote(freq, melT, dur * 0.85, vel);
                }
                melT += dur;
            });

            // --- Acoustic upright bass (deep sine + slight growl) ---
            let bassT = now;
            data.bassLine.forEach(([freq, beats]) => {
                const dur = beats * beatSec;
                if (freq > 0) {
                    // Fundamental
                    const o = this.ctx.createOscillator();
                    const g = this.ctx.createGain();
                    o.type = 'sine';
                    o.frequency.value = freq;
                    const v = this.musicVol * 1.3;
                    g.gain.setValueAtTime(0.001, bassT);
                    g.gain.linearRampToValueAtTime(v, bassT + 0.012);
                    g.gain.setValueAtTime(v * 0.7, bassT + 0.05);
                    g.gain.exponentialRampToValueAtTime(v * 0.25, bassT + dur * 0.6);
                    g.gain.exponentialRampToValueAtTime(0.001, bassT + dur * 0.9);
                    const lp = this.ctx.createBiquadFilter();
                    lp.type = 'lowpass'; lp.frequency.value = 500;
                    o.connect(lp); lp.connect(g); g.connect(this.musicGain);
                    o.start(bassT); o.stop(bassT + dur);
                    this._musicNodes.push(o);

                    // String growl (triangle overtone)
                    const o2 = this.ctx.createOscillator();
                    const g2 = this.ctx.createGain();
                    o2.type = 'triangle';
                    o2.frequency.value = freq * 2;
                    g2.gain.setValueAtTime(0.001, bassT);
                    g2.gain.linearRampToValueAtTime(v * 0.12, bassT + 0.01);
                    g2.gain.exponentialRampToValueAtTime(0.001, bassT + dur * 0.3);
                    o2.connect(g2); g2.connect(this.musicGain);
                    o2.start(bassT); o2.stop(bassT + dur);
                    this._musicNodes.push(o2);

                    // Finger pluck transient
                    const pl = this.ctx.createOscillator();
                    const pg = this.ctx.createGain();
                    pl.type = 'square';
                    pl.frequency.value = freq * 4;
                    pg.gain.setValueAtTime(v * 0.15, bassT);
                    pg.gain.exponentialRampToValueAtTime(0.001, bassT + 0.012);
                    pl.connect(pg); pg.connect(this.musicGain);
                    pl.start(bassT); pl.stop(bassT + 0.02);
                    this._musicNodes.push(pl);
                }
                bassT += dur;
            });

            // --- Jazz drums (ride pattern + ghost notes + kick accents) ---
            for (let b = 0; b < totalBeats; b++) {
                const bt = now + b * beatSec;
                const swungBt = (b % 3 === 2) ? bt + beatSec * swing : bt;

                // Ride cymbal: classic jazz pattern (1 & a, 2 & a -- spang-a-lang)
                brushRide(bt, this.musicVol * 0.28);
                if (b % 2 === 0) {
                    brushRide(bt + beatSec * 0.66, this.musicVol * 0.15);
                }

                // Hi-hat pedal on 2 and 4
                if (b % 4 === 2 || b % 4 === 0) {
                    this._lofiHat(bt, this.musicVol * 0.12);
                }

                // Ghost snare (random brush swishes)
                if (b % 4 === 2) {
                    ghostSnare(bt + beatSec * 0.01, this.musicVol * 0.18);
                }
                if (Math.random() > 0.7 && b % 2 === 1) {
                    ghostSnare(swungBt, this.musicVol * 0.08);
                }

                // Kick: sparse, only on strong beats with variation
                if (b % 8 === 0) {
                    this._lofiKick(bt);
                }
                if (b % 8 === 6 && Math.random() > 0.4) {
                    this._lofiKick(bt);
                }
            }

            this._musicTimer = setTimeout(() => playLoop(), loopDur * 1000 - 200);
        };

        playLoop();
    },

    playMusic(phase) {
        if (this._currentPhase === phase && this._musicPlaying) return;
        this.stopMusic();
        this._currentPhase = phase;
        this._musicPlaying = true;

        if (phase === 'title') {
            // Chiptune arcade via Web Audio API
            this._init();
            this._playArcade();
        } else {
            // MP3 via HTML5 Audio for explore/challenge phases
            const audio = this._getAudio();
            audio.currentTime = 0;
            audio.volume = this.musicTargetVol;
            audio.play().catch(() => {
                // Autoplay blocked -- will start on next user interaction
                const resume = () => { audio.play(); document.removeEventListener('click', resume); document.removeEventListener('keydown', resume); };
                document.addEventListener('click', resume, { once: true });
                document.addEventListener('keydown', resume, { once: true });
            });
        }
    },

    stopMusic() {
        this._musicPlaying = false;
        this._currentPhase = null;
        this._musicPaused = false;
        // Stop Web Audio (arcade / SFX nodes)
        clearTimeout(this._musicTimer);
        this._musicNodes.forEach(n => { try { n.stop(); } catch (e) { } });
        this._musicNodes = [];
        this._crackleNode = null;
        // Stop MP3
        if (this._audioElement) {
            this._audioElement.pause();
            this._audioElement.currentTime = 0;
        }
    },

    /** Fade out MP3 / arcade music (seamless resume). */
    pauseMusic() {
        if (this._musicPaused) return;
        this._musicPaused = true;
        if (this._audioElement && !this._audioElement.paused) {
            // Fade out MP3 volume over 300ms
            const audio = this._audioElement;
            const fadeFrom = Math.max(audio.volume, this.musicTargetVol);
            const step = fadeFrom / 15;
            const fade = setInterval(() => {
                if (audio.volume > step) { audio.volume = Math.max(0, audio.volume - step); }
                else { audio.volume = 0; audio.pause(); clearInterval(fade); }
            }, 20);
        } else if (this.ctx && this.musicGain) {
            // Fade out Web Audio (arcade)
            const t = this.ctx.currentTime;
            this.musicGain.gain.cancelScheduledValues(t);
            this.musicGain.gain.setValueAtTime(this.musicGain.gain.value, t);
            this.musicGain.gain.linearRampToValueAtTime(0.0001, t + 0.3);
        }
    },

    /** Fade music back in (seamless resume after pause). */
    resumeMusic() {
        if (!this._musicPaused) return;
        this._musicPaused = false;
        if (this._audioElement) {
            // Fade in MP3 volume back to the in-game target.
            this._audioElement.volume = 0;
            this._audioElement.play().catch(() => { });
            const audio = this._audioElement;
            const target = this.musicTargetVol;
            const step = target / 15;
            const fade = setInterval(() => {
                if (audio.volume < target - step) { audio.volume = Math.min(target, audio.volume + step); }
                else { audio.volume = target; clearInterval(fade); }
            }, 20);
        } else if (this.ctx && this.musicGain) {
            // Fade in Web Audio (arcade)
            const t = this.ctx.currentTime;
            this.musicGain.gain.cancelScheduledValues(t);
            this.musicGain.gain.setValueAtTime(this.musicGain.gain.value, t);
            this.musicGain.gain.linearRampToValueAtTime(1.0, t + 0.3);
        }
    },
};

// ---- game state ----
const State = {
    sessionId: null,
    player: null,
    challenges: [],
    currentChallenge: null,
    avatarIndex: 0,
    isInDialog: false,
    isInChallenge: false,
    isBookPopup: false,
    isInPrep: false,
    paused: false,
    interactionTarget: null,
    _pendingNpcRegion: null,
    collectedBooks: [],
    // Company lock system
    lockedRegion: null,      // region name when inside a company
    lockedNpc: null,          // NPC data of current company founder
    enteringDoor: false,      // true during door enter animation
    doorAnimProgress: 0,      // 0..1 animation progress
    doorAnimBuilding: null,   // building being entered
    companyComplete: false,   // true when all challenges done in locked region
    completedRegions: [],     // list of fully completed region names
    learning: {
        stageBriefingsSeen: [],
        companyPrepSeen: [],
        livePrepSeen: [],
    },
    _actionCooldownUntil: 0,  // timestamp: ignore action keys until this time
};

// ---- NPC definitions ----
const NPC_DATA = [
    // -- INTERN --
    {
        id: 'npc_xerox', name: 'CHARLES GESCHKE', role: 'Cofundador - Xerox PARC / Adobe', region: 'Xerox PARC', stage: 'Intern', worldX: 800,
        dialog: 'Eu sou Charles Geschke. Nos anos 70, a Xerox PARC inventou a interface gr\u00e1fica, o mouse e a rede Ethernet -- tecnologias que mudaram o mundo. Mais tarde cofundei a Adobe e criamos o PostScript e o PDF. Aqui voc\u00ea vai provar que domina os fundamentos: l\u00f3gica, vari\u00e1veis e estruturas b\u00e1sicas. Sem base s\u00f3lida, nenhum sistema sobrevive.',
        look: { hair: '#ccc', hairStyle: 'bald-sides', beard: '#aaa', glasses: true, glassesStyle: 'round', shirt: '#1e3a5f', pants: '#333', skinTone: '#F5D0A9' }
    },
    {
        id: 'npc_apple', name: 'STEVE JOBS', role: 'Cofundador - Apple', region: 'Apple Garage', stage: 'Intern', worldX: 2200,
        dialog: 'Sou Steve Jobs. Em 1976, Steve Wozniak e eu montamos o primeiro Apple numa garagem em Los Altos, Calif\u00f3rnia. A Apple revolucionou a computa\u00e7\u00e3o pessoal, a m\u00fasica digital e os smartphones. Eu acreditava que tecnologia e arte devem andar juntas. Seus desafios aqui testar\u00e3o sua capacidade de pensar simples -- porque simplicidade \u00e9 a sofistica\u00e7\u00e3o suprema.',
        look: { hair: '#222', hairStyle: 'short', beard: null, glasses: true, glassesStyle: 'round', shirt: '#111', pants: '#3b5998', skinTone: '#F5D0A9', turtleneck: true }
    },
    // -- JUNIOR --
    {
        id: 'npc_microsoft', name: 'BILL GATES', role: 'Cofundador - Microsoft', region: 'Microsoft', stage: 'Junior', worldX: 3600,
        dialog: 'Prazer, Bill Gates. Em 1975, Paul Allen e eu fundamos a Microsoft com a vis\u00e3o de colocar um computador em cada mesa. Do MS-DOS ao Windows, do Office ao Azure -- constru\u00edmos um ecossistema que conecta bilh\u00f5es de pessoas. Como Junior, voc\u00ea precisa provar que entende sistemas operacionais, estruturas de dados e a base da engenharia de software.',
        look: { hair: '#8B6F47', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#4a90d9', pants: '#2c3e50', skinTone: '#F5D0A9', tie: '#8b0000' }
    },
    {
        id: 'npc_nubank', name: 'DAVID VELEZ', role: 'Fundador - Nubank', region: 'Nubank', stage: 'Junior', worldX: 5000,
        dialog: 'Ol\u00e1, sou David Velez. Fundei o Nubank em 2013 no Brasil porque estava cansado da burocracia banc\u00e1ria. Com um cart\u00e3o roxo e um app, democratizamos servi\u00e7os financeiros para mais de 80 milh\u00f5es de clientes. Fintech \u00e9 sobre eliminar complexidade e entregar valor real. Mostre que voc\u00ea sabe resolver problemas com c\u00f3digo limpo e eficiente.',
        look: { hair: '#222', hairStyle: 'short', beard: null, glasses: false, shirt: '#820ad1', pants: '#222', skinTone: '#D2A673', casual: true }
    },
    {
        id: 'npc_disney', name: 'BOB IGER', role: 'CEO - Disney', region: 'Disney', stage: 'Junior', worldX: 6400,
        dialog: 'Bob Iger, CEO da Walt Disney Company. De parques tem\u00e1ticos a Marvel, Star Wars e Pixar -- a Disney \u00e9 o maior conglomerado de entretenimento do mundo. Engenharia de software na Disney significa sistemas que encantam bilh\u00f5es de pessoas. Orienta\u00e7\u00e3o a objetos \u00e9 a base: interfaces, polimorfismo e heran\u00e7a. Mostre que voc\u00ea domina OOP.',
        look: { hair: '#bbb', hairStyle: 'parted', beard: null, glasses: false, shirt: '#1a237e', pants: '#111', skinTone: '#F5D0A9', suit: '#1a237e', tie: '#cc0000' }
    },
    // -- MID --
    {
        id: 'npc_google', name: 'LARRY & SERGEY', role: 'Cofundadores - Google', region: 'Google', stage: 'Mid', worldX: 7800,
        dialog: 'Somos Larry Page e Sergey Brin. Em 1998, numa garagem em Menlo Park, criamos o Google -- um buscador que organizou toda a informa\u00e7\u00e3o do mundo. Depois veio o Android, YouTube, Cloud, computacao. Como engenheiro Pleno, voc\u00ea enfrentar\u00e1 algoritmos avan\u00e7ados, sistemas distribu\u00eddos e a complexidade computacional que faz o Google funcionar em escala planet\u00e1ria.',
        look: { hair: '#333', hairStyle: 'curly', beard: null, glasses: false, shirt: '#4285f4', pants: '#333', skinTone: '#F5D0A9', casual: true }
    },
    {
        id: 'npc_facebook', name: 'MARK ZUCKERBERG', role: 'Cofundador - Facebook', region: 'Facebook', stage: 'Mid', worldX: 9200,
        dialog: 'Eu sou Mark Zuckerberg. Em 2004, no dormit\u00f3rio de Harvard, criei o Facebook. Hoje a Meta conecta mais de 3 bilh\u00f5es de pessoas e est\u00e1 construindo o metaverso. Escalar grafos sociais para esse volume exige engenharia de dados, consist\u00eancia eventual e arquitetura de sistemas que n\u00e3o falham. Prepare-se para desafios de n\u00edvel Pleno.',
        look: { hair: '#8B6F47', hairStyle: 'curly-short', beard: null, glasses: false, shirt: '#888', pants: '#333', skinTone: '#F5D0A9', hoodie: '#444' }
    },
    {
        id: 'npc_ibm', name: 'ARVIND KRISHNA', role: 'CEO - IBM', region: 'IBM', stage: 'Mid', worldX: 10600,
        dialog: 'Arvind Krishna, CEO da IBM. Desde 1911, a IBM define a computa\u00e7\u00e3o: mainframes, COBOL, SQL, Watson, computa\u00e7\u00e3o qu\u00e2ntica. Somos a empresa que inventou o c\u00f3digo de barras, o caixa eletr\u00f4nico e o disco r\u00edgido. Validar express\u00f5es, parsing e manipula\u00e7\u00e3o de estruturas -- esses s\u00e3o os fundamentos que todo engenheiro IBM domina.',
        look: { hair: '#333', hairStyle: 'short', beard: null, glasses: true, glassesStyle: 'square', shirt: '#0530ad', pants: '#222', skinTone: '#C68642', suit: '#0530ad', tie: '#fff' }
    },
    // -- SENIOR --
    {
        id: 'npc_amazon', name: 'JEFF BEZOS', role: 'Fundador - Amazon', region: 'Amazon', stage: 'Senior', worldX: 12000,
        dialog: 'Jeff Bezos aqui. Comecei a Amazon em 1994 vendendo livros numa garagem em Seattle. Hoje somos o maior e-commerce do planeta e a AWS \u00e9 a espinha dorsal da internet moderna. De e-commerce a cloud computing, aqui voc\u00ea projetar\u00e1 sistemas resilientes, com toler\u00e2ncia a falhas e alta disponibilidade. Engenheiro S\u00eanior n\u00e3o aceita sistema que cai.',
        look: { hair: null, hairStyle: 'bald', beard: null, glasses: false, shirt: '#1a3c5e', pants: '#222', skinTone: '#F5D0A9', bald: true }
    },
    {
        id: 'npc_meli', name: 'MARCOS GALPERIN', role: 'Fundador - Mercado Livre', region: 'Mercado Livre', stage: 'Senior', worldX: 13400,
        dialog: 'Sou Marcos Galperin. Fundei o Mercado Livre em 1999 na Argentina. Somos o maior ecossistema de com\u00e9rcio eletr\u00f4nico da Am\u00e9rica Latina -- marketplace, pagamentos com Mercado Pago, log\u00edstica e cr\u00e9dito. Processamos milh\u00f5es de transa\u00e7\u00f5es por segundo em 18 pa\u00edses. Seus desafios aqui envolvem escala, performance e arquitetura de plataforma.',
        look: { hair: '#555', hairStyle: 'short', beard: null, glasses: false, shirt: '#333', pants: '#222', skinTone: '#F5D0A9', suit: '#1a1a1a' }
    },
    {
        id: 'npc_jpmorgan', name: 'JAMIE DIMON', role: 'CEO - JP Morgan', region: 'JP Morgan', stage: 'Senior', worldX: 14800,
        dialog: 'Jamie Dimon, CEO do JP Morgan Chase -- o maior banco dos Estados Unidos, com mais de 200 anos de hist\u00f3ria. Wall Street exige zero toler\u00e2ncia a falhas. Cada transa\u00e7\u00e3o financeira \u00e9 irrevog\u00e1vel, cada microssegundo conta. Aqui voc\u00ea enfrentar\u00e1 desafios de sistemas cr\u00edticos, concorr\u00eancia e seguran\u00e7a de n\u00edvel banc\u00e1rio.',
        look: { hair: '#888', hairStyle: 'parted', beard: null, glasses: false, shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#0a3d62', tie: '#c9a800' }
    },
    {
        id: 'npc_paypal', name: 'PETER THIEL', role: 'Cofundador - PayPal', region: 'PayPal', stage: 'Senior', worldX: 16200,
        dialog: 'Peter Thiel. Cofundei o PayPal em 1998 com Max Levchin e Elon Musk. Criamos o pagamento digital que revolucionou o com\u00e9rcio online. A "M\u00e1fia do PayPal" gerou Tesla, LinkedIn, YouTube e Palantir. Detec\u00e7\u00e3o de fraude, processamento de strings e otimiza\u00e7\u00e3o de busca s\u00e3o essenciais quando cada transa\u00e7\u00e3o vale dinheiro real.',
        look: { hair: '#8B6F47', hairStyle: 'short', beard: null, glasses: false, shirt: '#003087', pants: '#222', skinTone: '#F5D0A9', suit: '#333' }
    },
    {
        id: 'npc_netflix', name: 'REED HASTINGS', role: 'Fundador - Netflix', region: 'Netflix', stage: 'Senior', worldX: 17600,
        dialog: 'Reed Hastings, fundador da Netflix. Em 1997, come\u00e7amos enviando DVDs pelo correio. Hoje transmitimos conte\u00fado para 260 milh\u00f5es de assinantes em 190 pa\u00edses. Nosso algoritmo de recomenda\u00e7\u00e3o \u00e9 lend\u00e1rio. Sliding window, processamento de streams e otimiza\u00e7\u00e3o de dados em tempo real -- \u00e9 isso que mant\u00e9m o mundo assistindo.',
        look: { hair: '#888', hairStyle: 'bald-sides', beard: null, glasses: false, shirt: '#e50914', pants: '#222', skinTone: '#F5D0A9', casual: true }
    },
    // -- STAFF --
    {
        id: 'npc_spacex', name: 'GWYNNE SHOTWELL', role: 'Presidente & COO - SpaceX', region: 'SpaceX', stage: 'Staff', worldX: 19000,
        dialog: 'Gwynne Shotwell, Presidente e COO da SpaceX. Enquanto Elon sonha, eu fa\u00e7o os foguetes decolarem. J\u00e1 lan\u00e7amos mais de 200 miss\u00f5es orbitais com sucesso. Telemetria de foguetes gera milh\u00f5es de dados por segundo -- deduplica\u00e7\u00e3o, conjuntos e filtragem s\u00e3o quest\u00e3o de vida ou morte. HashSet n\u00e3o \u00e9 teoria aqui, \u00e9 sobreviv\u00eancia.',
        look: { hair: '#6B4226', hairStyle: 'parted', beard: null, glasses: false, shirt: '#fff', pants: '#222', skinTone: '#F5D0A9', jacket: '#1a1a1a' }
    },
    {
        id: 'npc_tesla', name: 'ELON MUSK', role: 'CEO - Tesla', region: 'Tesla', stage: 'Staff', worldX: 20400,
        dialog: 'Elon Musk. A Tesla revolucionou os carros el\u00e9tricos. De baterias a software de autonomia, cada sistema precisa ser otimizado ao extremo. Engenharia sob restri\u00e7\u00f5es extremas -- esse \u00e9 o padr\u00e3o aqui. Como Staff Engineer, voc\u00ea vai redesenhar sistemas complexos, otimizar para o imposs\u00edvel e liderar decis\u00f5es t\u00e9cnicas cr\u00edticas.',
        look: { hair: '#555', hairStyle: 'short', beard: null, glasses: false, shirt: '#111', pants: '#222', skinTone: '#F5D0A9', jacket: '#1a1a1a' }
    },
    {
        id: 'npc_itau', name: 'ROBERTO SETUBAL', role: 'Ex-CEO - Ita\u00fa Unibanco', region: 'Itau', stage: 'Staff', worldX: 21800,
        dialog: 'Roberto Setubal, ex-CEO do Ita\u00fa Unibanco -- o maior banco privado do Brasil e da Am\u00e9rica Latina. Processamos trilh\u00f5es de reais por ano com sistemas que n\u00e3o podem parar. A transforma\u00e7\u00e3o digital de um banco centen\u00e1rio exige migrar legados para arquiteturas modernas sem interromper opera\u00e7\u00f5es. Desafios de Staff Engineer est\u00e3o \u00e0 sua espera.',
        look: { hair: '#aaa', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#003399', tie: '#ff6600' }
    },
    {
        id: 'npc_uber', name: 'TRAVIS KALANICK', role: 'Cofundador - Uber', region: 'Uber', stage: 'Staff', worldX: 23200,
        dialog: 'Travis Kalanick aqui. Cofundei a Uber em 2009 e transformamos o transporte global. Milh\u00f5es de corridas por minuto em centenas de cidades. Geolocaliza\u00e7\u00e3o em tempo real, matching de motoristas, precifica\u00e7\u00e3o din\u00e2mica, pagamentos -- tudo processado em milissegundos. Seus desafios envolvem sistemas real-time de alt\u00edssima performance.',
        look: { hair: '#333', hairStyle: 'short', beard: null, glasses: false, shirt: '#111', pants: '#222', skinTone: '#F5D0A9', casual: true }
    },
    {
        id: 'npc_nvidia', name: 'JENSEN HUANG', role: 'CEO - Nvidia', region: 'Nvidia', stage: 'Staff', worldX: 24600,
        dialog: 'Jensen Huang, CEO da Nvidia. Fundei a empresa em 1993 num Denny\'s em San Jose. De placas de video a computacao de alto desempenho, nossas GPUs movem simulacao, renderizacao e processamento massivo de dados. Ordenacao eficiente e pipelines robustos -- Merge Sort nao e exercicio academico, e o que roda em cada GPU nossa.',
        look: { hair: '#222', hairStyle: 'short', beard: null, glasses: false, shirt: '#111', pants: '#222', skinTone: '#D2A673', jacket: '#111' }
    },
    {
        id: 'npc_aurora_labs', name: 'SAM ALTMAN', role: 'CEO - Aurora Labs', region: 'Aurora Labs', stage: 'Staff', worldX: 26000,
        dialog: 'Sam Altman, CEO da Aurora Labs. Construimos plataformas de software em escala global, com pipelines de dados e servicos distribuidos. Grafos sao estruturas computacionais centrais. Travessia em largura, busca em profundidade e processamento de estruturas conectadas sustentam sistemas criticos. Grafos nao sao teoria, sao a realidade da computacao.',
        look: { hair: '#c4733c', hairStyle: 'short', beard: null, glasses: false, shirt: '#444', pants: '#333', skinTone: '#F5D0A9', casual: true }
    },
    // -- PRINCIPAL --
    {
        id: 'npc_santander', name: 'ANA BOTIN', role: 'CEO - Santander', region: 'Santander', stage: 'Principal', worldX: 27400,
        dialog: 'Ana Botin, CEO do Grupo Santander -- um dos maiores bancos do mundo, presente em dezenas de pa\u00edses. Banking global exige compliance com regula\u00e7\u00f5es como PCI DSS, PSD2, LGPD e Basel III simultaneamente. Zero margem de erro, auditoria total. Como Principal Engineer, seus desafios s\u00e3o de governan\u00e7a, seguran\u00e7a e arquitetura regulat\u00f3ria.',
        look: { hair: '#8B4513', hairStyle: 'parted', beard: null, glasses: false, shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#ec0000' }
    },
    {
        id: 'npc_bradesco', name: 'MARCELO NORONHA', role: 'CEO - Bradesco', region: 'Bradesco', stage: 'Principal', worldX: 28800,
        dialog: 'Marcelo Noronha, CEO do Bradesco. Somos um dos maiores bancos do Brasil, com mais de 70 milh\u00f5es de clientes. A transforma\u00e7\u00e3o digital de um banco dessa escala -- de ag\u00eancias f\u00edsicas a APIs abertas, Open Banking e Pix -- exige vis\u00e3o arquitetural profunda. Seus desafios de Principal Engineer envolvem design de sistemas que definem o futuro financeiro.',
        look: { hair: '#555', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#cc092f', tie: '#cc092f' }
    },
    {
        id: 'npc_gemini', name: 'DEMIS HASSABIS', role: 'CEO - Google DeepMind', region: 'Gemini', stage: 'Principal', worldX: 30200,
        dialog: 'Demis Hassabis, CEO do Google DeepMind. Lideramos pesquisa e produtos de computacao em larga escala, da ciencia aplicada a sistemas de decisao. Priority Queue e Heap sao fundamentais em computacao: agendamento de tarefas, busca A* e processamento por prioridade. Quando cada decisao tem um custo, priorizar e tudo.',
        look: { hair: '#333', hairStyle: 'curly', beard: null, glasses: false, shirt: '#4285f4', pants: '#222', skinTone: '#D2A673', casual: true }
    },
    {
        id: 'npc_nexus_labs', name: 'DARIO AMODEI', role: 'CEO - Anthropic', region: 'Nexus Labs', stage: 'Principal', worldX: 31600,
        dialog: 'Dario Amodei, CEO da Anthropic, criadores do Nexus Labs. Sa\u00ed da Aurora Labs para construir computacao segura e alinhada. Programa\u00e7\u00e3o din\u00e2mica \u00e9 o cora\u00e7\u00e3o do racioc\u00ednio: decompor problemas grandes em subproblemas menores, memorizar resultados e construir a solu\u00e7\u00e3o de baixo para cima. \u00c9 assim que o Nexus Labs pensa -- e \u00e9 assim que voc\u00ea vai pensar.',
        look: { hair: '#333', hairStyle: 'curly', beard: '#333', glasses: true, glassesStyle: 'round', shirt: '#d4a574', pants: '#333', skinTone: '#F5D0A9' }
    },
    {
        id: 'npc_cloud', name: 'LINUS TORVALDS', role: 'Criador - Linux / Git', region: 'Cloud Valley', stage: 'Principal', worldX: 33000,
        dialog: 'Linus Torvalds. Criei o Linux em 1991, o sistema operacional que roda em servidores, smartphones e supercomputadores. Depois criei o Git, que revolucionou o controle de vers\u00e3o. Voc\u00ea chegou ao topo da jornada. Aqui criamos contratos para o futuro -- open source, infraestrutura global e os alicerces da computa\u00e7\u00e3o moderna.',
        look: { hair: '#c4a35a', hairStyle: 'short', beard: '#b8963e', glasses: true, glassesStyle: 'square', shirt: '#2d5016', pants: '#3b3b3b', skinTone: '#F5D0A9' }
    },
];

// ---- buildings / zones ----
const BUILDINGS = [
    { name: 'XEROX PARC', x: 500, w: 400, h: 200, color: '#94a3b8', roofColor: '#64748b' },
    { name: 'APPLE GARAGE', x: 1900, w: 350, h: 160, color: '#ef4444', roofColor: '#b91c1c' },
    { name: 'MICROSOFT', x: 3300, w: 500, h: 280, color: '#0078d4', roofColor: '#005a9e' },
    { name: 'NUBANK', x: 4700, w: 420, h: 240, color: '#820ad1', roofColor: '#5b0894' },
    { name: 'DISNEY', x: 6100, w: 450, h: 250, color: '#1a237e', roofColor: '#0d1242' },
    { name: 'GOOGLE', x: 7500, w: 550, h: 250, color: '#4285f4', roofColor: '#2b5ea7' },
    { name: 'FACEBOOK', x: 8900, w: 450, h: 260, color: '#1877f2', roofColor: '#0d5bbd' },
    { name: 'IBM', x: 10300, w: 480, h: 270, color: '#0530ad', roofColor: '#031f7a' },
    { name: 'AMAZON', x: 11700, w: 500, h: 300, color: '#ff9900', roofColor: '#cc7a00' },
    { name: 'MERCADO LIVRE', x: 13100, w: 480, h: 270, color: '#ffe600', roofColor: '#ccb800' },
    { name: 'JP MORGAN', x: 14500, w: 520, h: 310, color: '#0a3d62', roofColor: '#072a44' },
    { name: 'PAYPAL', x: 15900, w: 460, h: 260, color: '#003087', roofColor: '#001f5c' },
    { name: 'NETFLIX', x: 17300, w: 480, h: 270, color: '#e50914', roofColor: '#b3070f' },
    { name: 'SPACEX', x: 18700, w: 550, h: 320, color: '#111111', roofColor: '#000000' },
    { name: 'TESLA', x: 20100, w: 600, h: 320, color: '#cc0000', roofColor: '#990000' },
    { name: 'ITAU', x: 21500, w: 460, h: 280, color: '#003399', roofColor: '#002266' },
    { name: 'UBER', x: 22900, w: 440, h: 260, color: '#000000', roofColor: '#1a1a1a' },
    { name: 'NVIDIA', x: 24300, w: 500, h: 290, color: '#76b900', roofColor: '#5a8c00' },
    { name: 'AURORA LABS', x: 25700, w: 480, h: 270, color: '#412991', roofColor: '#2d1b66' },
    { name: 'SANTANDER', x: 27100, w: 500, h: 290, color: '#ec0000', roofColor: '#b30000' },
    { name: 'BRADESCO', x: 28500, w: 480, h: 280, color: '#cc092f', roofColor: '#990720' },
    { name: 'GEMINI', x: 29900, w: 480, h: 280, color: '#4285f4', roofColor: '#2b5ea7' },
    { name: 'NEXUS LABS', x: 31300, w: 480, h: 280, color: '#d4a574', roofColor: '#b8895c' },
    { name: 'CLOUD VALLEY', x: 32700, w: 650, h: 350, color: '#8b5cf6', roofColor: '#6d28d9' },
];

// ---- company logos (Unicode text rendered above signs) ----
const COMPANY_LOGOS = {
    'XEROX PARC': { icon: 'X', font: 'bold 28px serif' },
    'APPLE GARAGE': { icon: '', font: '32px sans-serif', customDraw: 'apple' },
    'MICROSOFT': { icon: '', font: '26px sans-serif', customDraw: 'microsoft' },
    'NUBANK': { icon: 'Nu', font: 'bold 22px sans-serif' },
    'DISNEY': { icon: '', font: '28px serif', customDraw: 'disney' },
    'GOOGLE': { icon: '', font: 'bold 30px sans-serif', customDraw: 'google' },
    'FACEBOOK': { icon: 'f', font: 'bold 30px sans-serif' },
    'IBM': { icon: 'IBM', font: 'bold 20px monospace' },
    'AMAZON': { icon: '', font: 'bold 16px sans-serif', customDraw: 'amazon' },
    'MERCADO LIVRE': { icon: '', font: 'bold 22px sans-serif', customDraw: 'mercadolivre' },
    'JP MORGAN': { icon: 'JPM', font: 'bold 18px serif' },
    'PAYPAL': { icon: '', font: 'bold 22px sans-serif', customDraw: 'paypal' },
    'NETFLIX': { icon: 'N', font: 'bold 30px sans-serif' },
    'SPACEX': { icon: '', font: 'bold 28px sans-serif', customDraw: 'spacex' },
    'TESLA': { icon: 'T', font: 'bold 30px sans-serif' },
    'ITAU': { icon: '', font: 'bold 28px serif', customDraw: 'itau' },
    'UBER': { icon: '', font: 'bold 28px sans-serif', noLogo: true },
    'NVIDIA': { icon: '\u25B6', font: 'bold 26px sans-serif' },
    'AURORA LABS': { icon: '', font: '26px sans-serif', customDraw: 'aurora_labs' },
    'SANTANDER': { icon: 'S', font: 'bold 28px sans-serif' },
    'BRADESCO': { icon: 'B', font: 'bold 28px serif' },
    'GEMINI': { icon: '\u2733', font: '26px sans-serif' },
    'NEXUS LABS': { icon: 'C', font: 'bold 28px sans-serif' },
    'CLOUD VALLEY': { icon: '\u2601', font: '26px sans-serif' },
};

// ---- collectible books ----
const BOOKS_DATA = [
    {
        id: 'b01', title: 'Clean Code', author: 'Robert C. Martin', color: '#22c55e',
        summary: 'Código é um ativo de longo prazo. Legibilidade > esperteza. Funções pequenas, nomes claros, responsabilidade única e testes automatizados.',
        lesson: 'Código é para humanos primeiro; manutenção custa mais que escrever.',
        worldX: 400, floatY: 130
    },
    {
        id: 'b02', title: 'The Clean Coder', author: 'Robert C. Martin', color: '#16a34a',
        summary: 'Profissionalismo em engenharia. Disciplina, estimativas realistas, dizer "não", foco, prática deliberada e responsabilidade pessoal pela qualidade.',
        lesson: 'Ser sênior não é saber mais tecnologia, é assumir compromisso com entrega previsível e qualidade.',
        worldX: 700, floatY: 150
    },
    {
        id: 'b03', title: 'Clean Architecture', author: 'Robert C. Martin', color: '#15803d',
        summary: 'Arquitetura orientada a independência: do framework, do banco, da UI e de detalhes externos. Dependências apontam para o domínio.',
        lesson: 'O negócio é o núcleo; tecnologia é detalhe substituível.',
        worldX: 1200, floatY: 140
    },
    {
        id: 'b04', title: 'Design Patterns', author: 'GoF (Gang of Four)', color: '#3b82f6',
        summary: 'Catálogo de soluções recorrentes para problemas clássicos de design orientado a objetos. Ensina quando abstrair, desacoplar e reutilizar.',
        lesson: 'Não reinventar a roda; use padrões para reduzir complexidade e acoplamento.',
        worldX: 2000, floatY: 160
    },
    {
        id: 'b05', title: 'Refactoring', author: 'Martin Fowler', color: '#6366f1',
        summary: 'Melhorar código sem alterar comportamento. Pequenas mudanças contínuas mantém o sistema saudável.',
        lesson: 'Dívida técnica cresce em silêncio; refatorar é manutenção estratégica, não luxo.',
        worldX: 2600, floatY: 130
    },
    {
        id: 'b06', title: 'Domain-Driven Design', author: 'Eric Evans', color: '#8b5cf6',
        summary: 'Modelar software a partir do domínio do negócio, usando linguagem ubíqua e limites claros (Bounded Contexts).',
        lesson: 'Software complexo falha quando a tecnologia ignora o negócio.',
        worldX: 3500, floatY: 150
    },
    {
        id: 'b07', title: 'Implementing DDD', author: 'Vaughn Vernon', color: '#7c3aed',
        summary: 'Versão prática do DDD: agregados, eventos de domínio, consistência, microsserviços orientados a contexto.',
        lesson: 'Limites bem definidos evitam sistemas distribuídos caóticos.',
        worldX: 4200, floatY: 140
    },
    {
        id: 'b08', title: 'Designing Data-Intensive Apps', author: 'Martin Kleppmann', color: '#ef4444',
        summary: 'Bíblia de sistemas distribuídos: consistência, replicação, particionamento, tolerância a falhas, trade-offs CAP.',
        lesson: 'Escala é sobre trade-offs; não existe sistema distribuído perfeito.',
        worldX: 5100, floatY: 160
    },
    {
        id: 'b09', title: 'Building Microservices', author: 'Sam Newman', color: '#f97316',
        summary: 'Como decompor sistemas, evitar acoplamento e gerenciar comunicação, deploy e governança.',
        lesson: 'Microsserviços só funcionam com autonomia, observabilidade e cultura madura.',
        worldX: 5700, floatY: 130
    },
    {
        id: 'b10', title: 'Release It!', author: 'Michael Nygard', color: '#dc2626',
        summary: 'Sistemas falham em produção por causas previsíveis. Circuit breaker, bulkhead, retry, timeout e padrões de resiliência.',
        lesson: 'Projetar para falhar é o único caminho para estabilidade.',
        worldX: 6500, floatY: 150
    },
    {
        id: 'b11', title: 'Site Reliability Engineering', author: 'Google SRE Team', color: '#fbbf24',
        summary: 'Operar sistemas como engenharia: SLO, error budget, automação, redução de toil.',
        lesson: 'Confiabilidade é uma métrica de negócio, não apenas técnica.',
        worldX: 7200, floatY: 140
    },
    {
        id: 'b12', title: 'The Phoenix Project', author: 'Gene Kim', color: '#f59e0b',
        summary: 'Romance sobre transformação DevOps. Mostra gargalos, fluxo, dependências e melhoria contínua.',
        lesson: 'TI é sistema de produção; otimizar o fluxo gera resultado real.',
        worldX: 8200, floatY: 160
    },
    {
        id: 'b13', title: 'The DevOps Handbook', author: 'Gene Kim', color: '#eab308',
        summary: 'Manual prático: CI/CD, infraestrutura como código, feedback rápido, cultura colaborativa.',
        lesson: 'Velocidade com qualidade só vem com automação e integração contínua.',
        worldX: 9500, floatY: 130
    },
    {
        id: 'b14', title: 'The Lean Startup', author: 'Eric Ries', color: '#ec4899',
        summary: 'Construir, medir, aprender. Validar hipóteses antes de escalar.',
        lesson: 'Não construa mais; aprenda mais rápido com o mercado.',
        worldX: 10200, floatY: 150
    },
    {
        id: 'b15', title: 'Measure What Matters', author: 'John Doerr', color: '#d946ef',
        summary: 'OKRs para alinhar estratégia e execução. Foco em resultados mensuráveis e prioridades claras.',
        lesson: 'O que não é medido não é gerenciado.',
        worldX: 11200, floatY: 140
    },
    {
        id: 'b16', title: 'Good Strategy Bad Strategy', author: 'Richard Rumelt', color: '#a855f7',
        summary: 'Estratégia real é diagnóstico + escolha clara + ações coerentes. Evita metas genéricas e slogans.',
        lesson: 'Estratégia é foco e renúncia, não ambição vaga.',
        worldX: 12800, floatY: 160
    },
    {
        id: 'b17', title: 'Cracking the Coding Interview', author: 'Gayle Laakmann McDowell', color: '#06b6d4',
        summary: 'Preparação para entrevistas técnicas: arrays, strings, árvores, grafos, recursão e complexidade algorítmica.',
        lesson: 'Entrevistas medem raciocínio, não decoreba. Pratique decomposição de problemas.',
        worldX: 13500, floatY: 130
    },
    {
        id: 'b18', title: 'Introduction to Algorithms', author: 'Cormen, Leiserson, Rivest, Stein', color: '#0891b2',
        summary: 'CLRS: a referência acadêmica em algoritmos. Ordenação, grafos, programação dinâmica, NP-completude.',
        lesson: 'Complexidade computacional define os limites do que é possível.',
        worldX: 14500, floatY: 150
    },
    {
        id: 'b19', title: 'System Design Interview', author: 'Alex Xu', color: '#14b8a6',
        summary: 'Como projetar sistemas escaláveis: load balancer, cache, CDN, sharding, message queue, rate limiter.',
        lesson: 'Design de sistemas é sobre trade-offs mensuráveis, não escolhas absolutas.',
        worldX: 15500, floatY: 140
    },
    {
        id: 'b20', title: 'Grokking Algorithms', author: 'Aditya Bhargava', color: '#10b981',
        summary: 'Algoritmos explicados visualmente: busca binária, BFS, Dijkstra, programação dinâmica, KNN.',
        lesson: 'Pensar algoritmicamente é mais importante que decorar implementações.',
        worldX: 16500, floatY: 160
    },
    {
        id: 'b21', title: 'Accelerate', author: 'Forsgren, Humble, Kim', color: '#84cc16',
        summary: 'Métricas DORA: frequência de deploy, lead time, MTTR, taxa de falha. Evidência científica para DevOps.',
        lesson: 'Performance de engenharia se mede com dados, não opinião.',
        worldX: 17500, floatY: 130
    },
    {
        id: 'b22', title: 'Staff Engineer', author: 'Will Larson', color: '#a3e635',
        summary: 'Além de sênior: influência técnica, mentoria, decisões arquiteturais, navegação organizacional.',
        lesson: 'Staff Engineer resolve problemas que nenhum time sozinho consegue.',
        worldX: 18500, floatY: 150
    },
    {
        id: 'b23', title: 'A Philosophy of Software Design', author: 'John Ousterhout', color: '#65a30d',
        summary: 'Complexidade e o inimigo. Modulos profundos, interfaces simples, abstrair o que importa.',
        lesson: 'Bom design e invisivel; mau design grita a cada mudanca.',
        worldX: 19500, floatY: 140
    },
];

// ---- learning framework: stage mindset + java prep + live coding playbook ----
const LEARNING_STAGE_ORDER = ['Intern', 'Junior', 'Mid', 'Senior', 'Staff', 'Principal', 'Distinguished'];
const LEARNING_STAGE_PT = {
    Intern: 'Estagiario',
    Junior: 'Junior',
    Mid: 'Pleno',
    Senior: 'Senior',
    Staff: 'Staff',
    Principal: 'Principal',
    Distinguished: 'CEO',
};

const LEARNING_STAGE_PROFILE = {
    Intern: {
        thinking: [
            'Transformar o enunciado em passos pequenos e claros.',
            'Nomear variaveis para explicar a intencao.',
            'Validar o resultado com exemplos simples.',
        ],
        concerns: [
            'Compilar sem erro de sintaxe.',
            'Entender classe, metodo main e tipos primitivos.',
            'Nao pular etapas do raciocinio.',
        ],
        javaFocus: [
            'Estrutura: class + public static void main(String[] args).',
            'Tipos primitivos e String com declaracao clara.',
            'if/for com chaves e ; corretos.',
        ],
    },
    Junior: {
        thinking: [
            'Escolher estrutura de dados antes de codar.',
            'Quebrar o problema em funcoes/metodos pequenos.',
            'Comparar alternativa simples vs alternativa eficiente.',
        ],
        concerns: [
            'Legibilidade e padrao de codigo do time.',
            'Complexidade O(n) vs O(n^2).',
            'Cobrir casos de borda basicos.',
        ],
        javaFocus: [
            'Classes e metodos com responsabilidade unica.',
            'Colecoes basicas: Array, List, Map, Set.',
            'Boas assinaturas de metodo e nomes consistentes.',
        ],
    },
    Mid: {
        thinking: [
            'Modelar entrada, processamento e saida explicitamente.',
            'Argumentar trade-off de memoria x tempo.',
            'Explicar por que a solucao escala para n maior.',
        ],
        concerns: [
            'Corretude em casos extremos.',
            'Design OO com baixo acoplamento.',
            'Padroes de iteracao e recursao sem bugs ocultos.',
        ],
        javaFocus: [
            'Interfaces, composicao e polimorfismo pratico.',
            'Collections e iteradores com uso correto.',
            'Tratamento de null e contratos de metodo.',
        ],
    },
    Senior: {
        thinking: [
            'Projetar para observabilidade e confiabilidade.',
            'Antecipar falha, concorrencia e regressao.',
            'Documentar decisao tecnica com criterio.',
        ],
        concerns: [
            'Disponibilidade e performance sob carga.',
            'Seguranca e consistencia de dados.',
            'Testabilidade e manutencao futura.',
        ],
        javaFocus: [
            'APIs coesas e contratos imutaveis quando possivel.',
            'Uso consciente de concorrencia e colecoes.',
            'Complexidade e custo operacional da solucao.',
        ],
    },
    Staff: {
        thinking: [
            'Ajustar arquitetura para varios times simultaneos.',
            'Definir guardrails tecnicos reutilizaveis.',
            'Transformar padrao local em pratica organizacional.',
        ],
        concerns: [
            'Padronizacao sem travar autonomia do time.',
            'Escalabilidade de codigo e de processo.',
            'Risco tecnico transversal entre servicos.',
        ],
        javaFocus: [
            'Abstracoes estaveis para varios modulos.',
            'Interfaces e contratos orientados a evolucao.',
            'Decisoes de estrutura de dados guiadas por dominio.',
        ],
    },
    Principal: {
        thinking: [
            'Resolver o problema sistemico, nao so o bug local.',
            'Construir direcao tecnica para trimestres/anos.',
            'Conectar engenharia, produto e risco regulatorio.',
        ],
        concerns: [
            'Trade-off entre velocidade, qualidade e governanca.',
            'Escala global, compliance e resiliencia.',
            'Capacidade da arquitetura de sobreviver a mudancas.',
        ],
        javaFocus: [
            'Boundary claro entre dominio e infraestrutura.',
            'Padroes de design para evolucao longa.',
            'Modelagem de dados orientada a invariantes.',
        ],
    },
    Distinguished: {
        thinking: [
            'Definir visao tecnica da organizacao.',
            'Elevar padrao de engenharia em toda empresa.',
            'Garantir continuidade de conhecimento.',
        ],
        concerns: [
            'Sustentabilidade tecnica de longo prazo.',
            'Excelencia de engenharia em escala.',
            'Formacao de liderancas tecnicas.',
        ],
        javaFocus: [
            'Arquitetura de referencia para toda plataforma.',
            'Decisoes tecnicas com impacto de negocio.',
            'Qualidade sistemica fim a fim.',
        ],
    },
};

const LEARNING_CATEGORY_GUIDE = {
    logic: 'Raciocinio passo a passo, condicoes e loops com ordem correta.',
    architecture: 'Trade-off tecnico, desacoplamento e impacto em escala.',
    domain_modeling: 'Classe, metodo e dados representando regras do negocio.',
    distributed_systems: 'Latencia, falha parcial, consistencia e resiliencia.',
};

// ---- world engine (canvas side-scroller) ----
const World = {
    canvas: null,
    ctx: null,
    W: 0,
    H: 0,
    GROUND_Y: 0,
    WORLD_WIDTH: 34000,
    camera: { x: 0 },
    running: false,
    lastTime: 0,
    stepTimer: 0,

    // Player physics
    player: {
        x: 100, y: 0, vx: 0, vy: 0,
        w: 48, h: 80,
        onGround: true,
        facing: 1, // 1=right, -1=left
        state: 'idle', // idle, walk, run, jump, fall
        animFrame: 0,
        animTimer: 0,
        skinIndex: 0,
    },

    keys: {},
    spriteImg: null,
    spriteLoaded: false,

    // Decoration
    clouds: [],
    trees: [],
    mountains: [],

    init(avatarIndex, startX = 100) {
        this.canvas = document.getElementById('gameCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.player.skinIndex = avatarIndex || 0;

        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Load sprite sheet
        this.spriteImg = new Image();
        this.spriteImg.onload = () => { this.spriteLoaded = true; };
        this.spriteImg.src = '/static/img.png';

        // Generate decorations
        this.generateDecorations();

        // Input
        this.setupInput();

        // Reset player with saved position
        this.player.x = startX;
        this.player.y = 0;
        this.player.vx = 0;
        this.player.vy = 0;
        this.player.onGround = true;
        this.player.facing = 1;
        this.player.state = 'idle';
        // Set camera to follow player position
        this.camera.x = Math.max(0, startX - this.W * 0.35);
    },

    resize() {
        this.W = window.innerWidth;
        this.H = window.innerHeight;
        this.canvas.width = this.W;
        this.canvas.height = this.H;
        const mobileControls = document.querySelector('.mobile-controls');
        const controlsVisible = mobileControls && getComputedStyle(mobileControls).display !== 'none';
        this.GROUND_Y = controlsVisible ? this.H - 160 : this.H - 80;
    },

    generateDecorations() {
        this.clouds = [];
        this.trees = [];
        this.mountains = [];

        // Clouds
        for (let i = 0; i < 40; i++) {
            this.clouds.push({
                x: Math.random() * this.WORLD_WIDTH,
                y: 30 + Math.random() * 120,
                w: 80 + Math.random() * 120,
                h: 30 + Math.random() * 30,
                speed: 0.1 + Math.random() * 0.3,
            });
        }

        // Trees
        for (let i = 0; i < 200; i++) {
            const tx = Math.random() * this.WORLD_WIDTH;
            // Avoid placing on top of buildings
            let onBuilding = false;
            for (const b of BUILDINGS) {
                if (tx > b.x - 20 && tx < b.x + b.w + 20) { onBuilding = true; break; }
            }
            if (!onBuilding) {
                this.trees.push({
                    x: tx,
                    h: 40 + Math.random() * 60,
                    trunkW: 6 + Math.random() * 4,
                    crownR: 18 + Math.random() * 20,
                    green: `hsl(${120 + Math.random() * 30}, ${60 + Math.random() * 20}%, ${30 + Math.random() * 15}%)`,
                });
            }
        }

        // Mountains (parallax background)
        for (let i = 0; i < 15; i++) {
            this.mountains.push({
                x: i * 1000 + Math.random() * 400,
                h: 150 + Math.random() * 200,
                w: 300 + Math.random() * 400,
                color: `hsl(220, ${10 + Math.random() * 10}%, ${60 + Math.random() * 15}%)`,
            });
        }
    },

    /* --- INPUT --- */
    setupInput() {
        document.addEventListener('keydown', e => {
            const prepOpen = Learning.isOpen();
            if (prepOpen) {
                if (e.code === 'Enter' || e.code === 'Space' || e.key === 'Escape') {
                    e.preventDefault();
                    Learning.continue();
                }
                return;
            }

            // If study chat is open, block world controls and allow ESC to close.
            if (StudyChat.isOpen()) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    StudyChat.close();
                }
                return;
            }

            // If IDE overlay is open, let the textarea handle all input
            const ideOpen = document.getElementById('ideOverlay') && document.getElementById('ideOverlay').classList.contains('visible');
            if (ideOpen) return;

            // TAB toggles the metrics overlay
            if (e.key === 'Tab') { e.preventDefault(); UI.toggleMetrics(); return; }

            // ESC: resume pause first; then close metrics overlay if open
            if (e.key === 'Escape' && State.paused) { e.preventDefault(); Game.resume(); return; }
            if (e.key === 'Escape' && UI._metricsOpen) { e.preventDefault(); UI.toggleMetrics(); return; }

            // P toggles pause (when world is active and no overlay is open)
            if ((e.key === 'p' || e.key === 'P') && !UI._metricsOpen) {
                e.preventDefault();
                if (State.paused) Game.resume(); else Game.pause();
                return;
            }

            // Block all game input while paused or metrics overlay is open
            if (State.paused) return;
            if (UI._metricsOpen) return;

            this.keys[e.code] = true;
            if (e.code === 'Enter' || e.code === 'Space') {
                if (performance.now() < State._actionCooldownUntil) return;
                const promoVisible = document.getElementById('promotionOverlay').style.display === 'flex';
                if (promoVisible) { UI.hidePromotion(); }
                else if (State.isBookPopup) { this.closeBookPopup(); }
                else if (State.isInDialog) { this.closeDialog(); }
                else if (!State.isInChallenge) { this.tryInteract(); }
            }
            // Prevent scroll
            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
        });
        document.addEventListener('keyup', e => {
            const prepOpen = Learning.isOpen();
            if (prepOpen) return;
            if (StudyChat.isOpen()) return;
            const ideOpen = document.getElementById('ideOverlay') && document.getElementById('ideOverlay').classList.contains('visible');
            if (ideOpen) return;
            // Release keys even if metrics open, to avoid stuck keys
            this.keys[e.code] = false;
        });

        // Mobile buttons -- hold-to-move with touchcancel safety
        const hold = (id, code) => {
            const el = document.getElementById(id);
            if (!el) return;
            const on = () => { if (State.paused || State.isInPrep) return; this.keys[code] = true; el.classList.add('pressed'); };
            const off = () => { this.keys[code] = false; el.classList.remove('pressed'); };
            el.addEventListener('mousedown', on);
            el.addEventListener('mouseup', off);
            el.addEventListener('mouseleave', off);
            el.addEventListener('touchstart', e => { e.preventDefault(); on(); }, { passive: false });
            el.addEventListener('touchend', e => { e.preventDefault(); off(); }, { passive: false });
            el.addEventListener('touchcancel', e => { e.preventDefault(); off(); }, { passive: false });
        };
        hold('btnLeft', 'ArrowLeft');
        hold('btnRight', 'ArrowRight');
        hold('btnJump', 'ArrowUp');

        const actBtn = document.getElementById('btnAction');
        if (actBtn) {
            const doAction = () => {
                if (State.paused) return;
                if (performance.now() < State._actionCooldownUntil) return;
                if (Learning.isOpen()) { Learning.continue(); return; }
                const promoVisible = document.getElementById('promotionOverlay').style.display === 'flex';
                if (promoVisible) UI.hidePromotion();
                else if (State.isBookPopup) this.closeBookPopup();
                else if (State.isInDialog) this.closeDialog();
                else if (!State.isInChallenge) this.tryInteract();
            };
            actBtn.addEventListener('click', doAction);
            actBtn.addEventListener('touchstart', e => { e.preventDefault(); doAction(); }, { passive: false });
        }

        // Prevent body scroll and bounce on iOS when touching the game canvas
        document.getElementById('gameCanvas').addEventListener('touchmove', e => e.preventDefault(), { passive: false });
    },

    /* --- INTERACTION (NPC proximity) --- */
    checkInteraction() {
        const p = this.player;
        let closest = null;
        let closestDist = 100;

        NPC_DATA.forEach(npc => {
            const dist = Math.abs(p.x + p.w / 2 - npc.worldX);
            if (dist < closestDist) {
                closestDist = dist;
                closest = npc;
            }
        });

        const hint = document.getElementById('interactHint');
        const isMobile = window.matchMedia('(max-width: 768px), (pointer: coarse)').matches;
        const keyCap = isMobile ? 'TOQUE' : 'ENTER';
        const actionBtn = document.getElementById('btnAction');

        if (closest && closestDist < 80) {
            State.interactionTarget = closest;
            hint.classList.add('visible');
            if (State.lockedRegion && closest.region !== State.lockedRegion) {
                document.getElementById('interactText').textContent = 'BLOQUEADO - Complete ' + State.lockedRegion;
                if (actionBtn) actionBtn.textContent = 'APRENDER';
            } else if (State.lockedRegion && closest.region === State.lockedRegion) {
                document.getElementById('interactText').textContent = 'CONTINUAR DESAFIOS COM ' + closest.name;
                if (actionBtn) actionBtn.textContent = 'APRENDER';
            } else {
                document.getElementById('interactText').textContent = 'APRENDER COM ' + closest.name;
                if (actionBtn) actionBtn.textContent = 'APRENDER';
            }
            // Update keycap label
            const keyCapEl = hint.querySelector('.key-cap');
            if (keyCapEl) keyCapEl.textContent = keyCap;
        } else {
            State.interactionTarget = null;
            hint.classList.remove('visible');
            if (actionBtn) actionBtn.textContent = 'APRENDER';
        }
    },

    tryInteract() {
        if (State.isInChallenge || State.isInDialog || State.enteringDoor || State.isInPrep) return;
        if (!State.interactionTarget) return;
        // If already locked in a company, prevent interaction with other NPCs
        if (State.lockedRegion && State.interactionTarget.region !== State.lockedRegion) {
            this.showDialog('SISTEMA', 'Bloqueado', 'Você precisa concluir todos os desafios em ' + State.lockedRegion + ' antes de sair. Resolva as questões e o desafio de código.');
            return;
        }

        const npc = State.interactionTarget;
        const stageOrder = ['Intern', 'Junior', 'Mid', 'Senior', 'Staff', 'Principal', 'Distinguished'];
        const playerIdx = stageOrder.indexOf(State.player.stage);
        const npcIdx = stageOrder.indexOf(npc.stage);

        SFX.npcInteract();
        SFX.talk();

        if (npcIdx > playerIdx) {
            this.showDialog(npc.name, npc.role, 'Você ainda não atingiu o cargo necessário para me desafiar. Continue evoluindo.');
            return;
        }

        // If region already fully completed, just greet
        if (State.completedRegions.includes(npc.region)) {
            this.showDialog(npc.name, npc.role, 'Você já completou todos os desafios aqui. Parabéns! Siga em frente para a próxima empresa.');
            return;
        }

        // If already locked in this same company, go directly to challenges (no door animation again)
        if (State.lockedRegion === npc.region) {
            State._pendingNpcRegion = npc.region;
            this.showDialog(npc.name, npc.role, 'Vamos continuar os desafios. Você ainda precisa completar tudo aqui.');
            return;
        }

        // Start door enter animation (first time entering)
        const building = BUILDINGS.find(b => b.name === npc.region || b.name.toUpperCase() === npc.region.toUpperCase());
        if (building) {
            State.enteringDoor = true;
            State.doorAnimProgress = 0;
            State.doorAnimBuilding = building;
            State.lockedNpc = npc;
            this._doorAnimStart = performance.now();
            this._doorAnimCallback = () => {
                State.enteringDoor = false;
                State.lockedRegion = npc.region;
                // Persist entry into company
                WorldStatePersistence.save(true);
                this.showDialog(npc.name, npc.role, npc.dialog + '\n\nVocê entrou na ' + npc.region + '. Resolva TODOS os desafios para poder sair.');
                State._pendingNpcRegion = npc.region;
            };
        } else {
            // Fallback if no building found
            State.lockedRegion = npc.region;
            State.lockedNpc = npc;
            // Persist entry into company
            WorldStatePersistence.save(true);
            this.showDialog(npc.name, npc.role, npc.dialog + '\n\nResolva TODOS os desafios para poder sair.');
            State._pendingNpcRegion = npc.region;
        }
    },

    showDialog(name, role, text) {
        State.isInDialog = true;
        State._actionCooldownUntil = performance.now() + 300;
        document.getElementById('dName').textContent = name;
        document.getElementById('dRole').textContent = role;
        document.getElementById('dContent').textContent = text;

        const av = document.getElementById('dAvatar');
        av.style.backgroundImage = 'none';
        av.textContent = name.charAt(0);

        document.getElementById('dialogBox').classList.add('open');
    },

    closeDialog() {
        State.isInDialog = false;
        document.getElementById('dialogBox').classList.remove('open');

        if (State._pendingNpcRegion) {
            const region = State._pendingNpcRegion;
            State._pendingNpcRegion = null;
            Game.enterRegion(region);
        }
    },

    /* --- PHYSICS & UPDATE --- */
    update(dt) {
        if (State.isInDialog || State.isInChallenge || State.isBookPopup || State.isInPrep) return;

        // Door enter animation
        if (State.enteringDoor) {
            const elapsed = (performance.now() - this._doorAnimStart) / 1000;
            State.doorAnimProgress = Math.min(elapsed / 1.2, 1); // 1.2 second animation
            // Move player toward door
            if (State.doorAnimBuilding) {
                const doorX = State.doorAnimBuilding.x + State.doorAnimBuilding.w / 2;
                const p = this.player;
                const dx = doorX - (p.x + p.w / 2);
                if (Math.abs(dx) > 3) {
                    p.x += dx * 0.08;
                    p.facing = dx > 0 ? 1 : -1;
                    p.state = 'walk';
                    p.animTimer += dt;
                    if (p.animTimer >= 0.14) { p.animTimer = 0; p.animFrame = (p.animFrame + 1) % 4; }
                }
                // Fade/shrink player as they enter
                if (State.doorAnimProgress > 0.6) {
                    p.state = 'idle';
                }
            }
            if (State.doorAnimProgress >= 1 && this._doorAnimCallback) {
                this._doorAnimCallback();
                this._doorAnimCallback = null;
            }
            return;
        }

        const p = this.player;
        const GRAVITY = 1800;
        const WALK_SPEED = 280;
        const RUN_SPEED = 450;
        const JUMP_FORCE = -800;

        // Horizontal
        const leftHeld = this.keys['ArrowLeft'] || this.keys['KeyA'];
        const rightHeld = this.keys['ArrowRight'] || this.keys['KeyD'];
        const runHeld = this.keys['ShiftLeft'] || this.keys['ShiftRight'];
        const jumpPressed = this.keys['ArrowUp'] || this.keys['KeyW'];

        const speed = runHeld ? RUN_SPEED : WALK_SPEED;
        if (leftHeld) { p.vx = -speed; p.facing = -1; }
        else if (rightHeld) { p.vx = speed; p.facing = 1; }
        else { p.vx *= 0.8; if (Math.abs(p.vx) < 5) p.vx = 0; }

        // Jump
        if (jumpPressed && p.onGround) {
            p.vy = JUMP_FORCE;
            p.onGround = false;
            SFX.jump();
            this.keys['ArrowUp'] = false;
            this.keys['KeyW'] = false;
        }

        // Gravity
        if (!p.onGround) {
            p.vy += GRAVITY * dt;
        }

        // Move
        p.x += p.vx * dt;
        p.y += p.vy * dt;

        // Ground collision
        if (p.y >= 0) {
            if (!p.onGround && p.vy > 100) SFX.land();
            p.y = 0;
            p.vy = 0;
            p.onGround = true;
        }

        // World bounds
        if (p.x < 0) p.x = 0;
        if (p.x > this.WORLD_WIDTH - p.w) p.x = this.WORLD_WIDTH - p.w;

        // Footstep sounds
        if (p.onGround && Math.abs(p.vx) > 50) {
            this.stepTimer += dt;
            const interval = runHeld ? 0.18 : 0.28;
            if (this.stepTimer >= interval) {
                this.stepTimer = 0;
                if (runHeld) SFX.run(); else SFX.step();
            }
        } else {
            this.stepTimer = 0;
        }

        // Animation state
        if (!p.onGround) {
            p.state = p.vy < 0 ? 'jump' : 'fall';
        } else if (Math.abs(p.vx) > 300) {
            p.state = 'run';
        } else if (Math.abs(p.vx) > 20) {
            p.state = 'walk';
        } else {
            p.state = 'idle';
        }

        // Animate frame
        p.animTimer += dt;
        const frameSpeed = p.state === 'run' ? 0.08 : 0.14;
        if (p.animTimer >= frameSpeed) {
            p.animTimer = 0;
            p.animFrame = (p.animFrame + 1) % 4;
        }

        // Book collision -- collect on touch (like Mario coins)
        // BLOCKED if player is locked inside a company
        if (!State.lockedRegion) {
            const pcx = p.x + p.w / 2;
            const playerHeight = -p.y; // height above ground (p.y is negative when jumping)
            BOOKS_DATA.forEach(book => {
                if (State.collectedBooks.includes(book.id)) return;
                const dx = Math.abs(pcx - book.worldX);
                const dy = Math.abs(playerHeight + p.h * 0.4 - book.floatY);
                if (dx < 40 && dy < 40) {
                    State.collectedBooks.push(book.id);
                    SFX.bookCollect();
                    this.showBookPopup(book);
                    this.updateBookHUD();
                    // Persist book collection immediately
                    WorldStatePersistence.save(true);
                }
            });
        }

        // Lock player movement to company area when locked
        if (State.lockedRegion && State.doorAnimBuilding) {
            const lb = State.doorAnimBuilding;
            const minX = lb.x - 60;
            const maxX = lb.x + lb.w + 60;
            if (p.x < minX) p.x = minX;
            if (p.x + p.w > maxX) p.x = maxX - p.w;
        }

        // Camera
        const targetCamX = p.x - this.W * 0.35;
        this.camera.x += (targetCamX - this.camera.x) * 0.1;
        if (this.camera.x < 0) this.camera.x = 0;
        if (this.camera.x > this.WORLD_WIDTH - this.W) this.camera.x = this.WORLD_WIDTH - this.W;

        // NPC check
        this.checkInteraction();
    },

    /* --- RENDERING --- */
    draw() {
        const ctx = this.ctx;
        const cam = this.camera.x;

        // Sky gradient
        const skyGrad = ctx.createLinearGradient(0, 0, 0, this.GROUND_Y);
        skyGrad.addColorStop(0, '#87CEEB');
        skyGrad.addColorStop(0.6, '#B0E0FF');
        skyGrad.addColorStop(1, '#E0F0FF');
        ctx.fillStyle = skyGrad;
        ctx.fillRect(0, 0, this.W, this.H);

        // Mountains (parallax 0.15)
        this.mountains.forEach(m => {
            const sx = m.x - cam * 0.15;
            if (sx + m.w < -100 || sx > this.W + 100) return;
            ctx.fillStyle = m.color;
            ctx.beginPath();
            ctx.moveTo(sx, this.GROUND_Y);
            ctx.lineTo(sx + m.w / 2, this.GROUND_Y - m.h);
            ctx.lineTo(sx + m.w, this.GROUND_Y);
            ctx.closePath();
            ctx.fill();
        });

        // Clouds (parallax 0.3)
        ctx.fillStyle = 'rgba(255,255,255,0.8)';
        this.clouds.forEach(c => {
            const sx = c.x - cam * 0.3;
            if (sx + c.w < -50 || sx > this.W + 50) return;
            ctx.beginPath();
            ctx.ellipse(sx + c.w / 2, c.y, c.w / 2, c.h / 2, 0, 0, Math.PI * 2);
            ctx.fill();
        });

        // Ground
        ctx.fillStyle = '#4ade80';
        ctx.fillRect(0, this.GROUND_Y, this.W, this.H - this.GROUND_Y);

        // Ground detail line
        ctx.fillStyle = '#22c55e';
        ctx.fillRect(0, this.GROUND_Y, this.W, 4);

        // Grass tufts
        ctx.fillStyle = '#16a34a';
        for (let gx = -cam % 30; gx < this.W; gx += 30) {
            ctx.fillRect(gx, this.GROUND_Y - 3, 2, 6);
            ctx.fillRect(gx + 8, this.GROUND_Y - 5, 2, 8);
            ctx.fillRect(gx + 15, this.GROUND_Y - 2, 2, 5);
        }

        // Trees
        this.trees.forEach(t => {
            const sx = t.x - cam;
            if (sx + t.crownR < -50 || sx - t.crownR > this.W + 50) return;

            // Trunk
            ctx.fillStyle = '#8B4513';
            ctx.fillRect(sx - t.trunkW / 2, this.GROUND_Y - t.h, t.trunkW, t.h);

            // Crown
            ctx.fillStyle = t.green;
            ctx.beginPath();
            ctx.arc(sx, this.GROUND_Y - t.h - t.crownR * 0.6, t.crownR, 0, Math.PI * 2);
            ctx.fill();
        });

        // Buildings
        BUILDINGS.forEach(b => {
            const sx = b.x - cam;
            if (sx + b.w < -10 || sx > this.W + 10) return;

            const by = this.GROUND_Y - b.h;

            // Building body
            ctx.fillStyle = b.color;
            ctx.fillRect(sx, by, b.w, b.h);

            // Roof
            ctx.fillStyle = b.roofColor;
            ctx.fillRect(sx - 10, by - 15, b.w + 20, 20);

            // Windows
            ctx.fillStyle = 'rgba(255,255,200,0.6)';
            const cols = Math.floor(b.w / 50);
            const rows = Math.floor(b.h / 60);
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    const wx = sx + 25 + c * 50;
                    const wy = by + 25 + r * 60;
                    ctx.fillRect(wx, wy, 25, 30);
                }
            }

            // Door -- enhanced with lock/open state visual
            const doorX = sx + b.w / 2 - 15;
            const doorY = this.GROUND_Y - 55;
            const doorW = 30;
            const doorH = 55;
            const isLockedHere = State.lockedRegion && (State.lockedRegion === b.name || State.lockedRegion.toUpperCase() === b.name.toUpperCase());
            const isCompleted = State.completedRegions.some(r => r.toUpperCase() === b.name.toUpperCase());
            const isDoorOpen = (State.enteringDoor && State.doorAnimBuilding === b && State.doorAnimProgress > 0.3);

            if (isDoorOpen) {
                // Open door: draw door frame + open door at angle
                ctx.fillStyle = '#1a1a1a';
                ctx.fillRect(doorX, doorY, doorW, doorH); // dark interior
                ctx.save();
                ctx.translate(doorX, doorY);
                ctx.transform(0.3, 0, 0, 1, 0, 0); // perspective skew
                ctx.fillStyle = '#6b4423';
                ctx.fillRect(0, 0, doorW, doorH);
                ctx.restore();
            } else {
                // Closed door
                ctx.fillStyle = isCompleted ? '#22c55e' : (isLockedHere ? '#ef4444' : '#6b4423');
                ctx.fillRect(doorX, doorY, doorW, doorH);
                // Door panels
                ctx.strokeStyle = 'rgba(0,0,0,0.3)';
                ctx.lineWidth = 1;
                ctx.strokeRect(doorX + 4, doorY + 4, doorW - 8, doorH / 2 - 6);
                ctx.strokeRect(doorX + 4, doorY + doorH / 2 + 2, doorW - 8, doorH / 2 - 6);
            }
            // Doorknob
            ctx.fillStyle = '#fbbf24';
            ctx.beginPath();
            ctx.arc(doorX + doorW - 7, doorY + doorH / 2, 3, 0, Math.PI * 2);
            ctx.fill();
            // Lock icon or check for locked/completed
            if (isLockedHere && !isDoorOpen) {
                ctx.fillStyle = '#fbbf24';
                ctx.font = 'bold 12px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('X', doorX + doorW / 2, doorY - 4);
                ctx.textAlign = 'left';
            } else if (isCompleted) {
                ctx.fillStyle = '#22c55e';
                ctx.font = 'bold 12px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('OK', doorX + doorW / 2, doorY - 4);
                ctx.textAlign = 'left';
            }

            // --- Corporate Sign / Placa Corporativa ---
            ctx.save();
            const signFont = 'bold 14px "JetBrains Mono", monospace';
            ctx.font = signFont;
            const textW = ctx.measureText(b.name).width;
            const signW = Math.max(textW + 40, 120);
            const signH = 32;
            const signX = sx + b.w / 2 - signW / 2;
            const signY = by - 18 - signH;
            const signR = 6;

            // Support poles (metal posts)
            const poleW = 4;
            const poleH = 14;
            const poleColor = '#94a3b8';
            const poleShadow = '#64748b';
            // Left pole
            ctx.fillStyle = poleShadow;
            ctx.fillRect(signX + 14, signY + signH, poleW + 1, poleH);
            ctx.fillStyle = poleColor;
            ctx.fillRect(signX + 14, signY + signH, poleW, poleH);
            // Right pole
            ctx.fillStyle = poleShadow;
            ctx.fillRect(signX + signW - 18, signY + signH, poleW + 1, poleH);
            ctx.fillStyle = poleColor;
            ctx.fillRect(signX + signW - 18, signY + signH, poleW, poleH);

            // Sign shadow (drop shadow behind)
            ctx.fillStyle = 'rgba(0,0,0,0.35)';
            this._roundRect(ctx, signX + 2, signY + 3, signW, signH, signR);
            ctx.fill();

            // Sign background (gradient panel)
            const signGrad = ctx.createLinearGradient(signX, signY, signX, signY + signH);
            signGrad.addColorStop(0, '#1e293b');
            signGrad.addColorStop(0.5, '#0f172a');
            signGrad.addColorStop(1, '#1e293b');
            ctx.fillStyle = signGrad;
            this._roundRect(ctx, signX, signY, signW, signH, signR);
            ctx.fill();

            // Sign border (subtle metallic frame)
            ctx.strokeStyle = '#475569';
            ctx.lineWidth = 1.5;
            this._roundRect(ctx, signX, signY, signW, signH, signR);
            ctx.stroke();

            // Inner highlight line (top shine)
            ctx.strokeStyle = 'rgba(148,163,184,0.3)';
            ctx.lineWidth = 1;
            this._roundRect(ctx, signX + 2, signY + 1, signW - 4, signH - 2, signR - 1);
            ctx.stroke();

            // Company color accent bar (thin strip at bottom)
            const accentH = 3;
            ctx.fillStyle = b.color;
            const accentY = signY + signH - accentH - 2;
            this._roundRect(ctx, signX + 8, accentY, signW - 16, accentH, 1.5);
            ctx.fill();

            // --- Company Logo above sign ---
            const logoData = COMPANY_LOGOS[b.name];
            if (logoData && !logoData.noLogo) {
                const logoCx = sx + b.w / 2;
                const logoR = 20;
                const logoCy = signY - logoR - 6;
                // Logo circle background
                ctx.fillStyle = '#0f172a';
                ctx.beginPath();
                ctx.arc(logoCx, logoCy, logoR + 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = b.color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(logoCx, logoCy, logoR + 2, 0, Math.PI * 2);
                ctx.stroke();
                // Company color fill inside circle
                ctx.fillStyle = b.color;
                ctx.globalAlpha = 0.15;
                ctx.beginPath();
                ctx.arc(logoCx, logoCy, logoR, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalAlpha = 1.0;
                // Logo icon (text or custom vector path)
                ctx.shadowColor = b.color;
                ctx.shadowBlur = 8;
                if (logoData.noLogo) {
                    // No logo badge for this company (e.g. Uber)
                } else if (logoData.customDraw) {
                    const drawFn = '_draw_' + logoData.customDraw;
                    if (this[drawFn]) this[drawFn](ctx, logoCx, logoCy, logoR, b.color);
                } else {
                    ctx.fillStyle = b.color;
                    ctx.font = logoData.font;
                    if (logoData.style === 'italic') ctx.font = 'italic ' + logoData.font;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    const iconTxt = logoData.icon;
                    ctx.fillText(iconTxt, logoCx, logoCy + 1);
                }
                ctx.shadowColor = 'transparent';
                ctx.shadowBlur = 0;
            }

            // Glow behind text (company color)
            ctx.shadowColor = b.color;
            ctx.shadowBlur = 12;
            ctx.shadowOffsetX = 0;
            ctx.shadowOffsetY = 0;

            // Company name text
            ctx.fillStyle = '#f1f5f9';
            ctx.font = signFont;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(b.name, sx + b.w / 2, signY + signH / 2);

            // Reset shadow and alignment
            ctx.shadowColor = 'transparent';
            ctx.shadowBlur = 0;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'alphabetic';
            ctx.restore();
        });

        // NPCs
        this.drawNPCs(cam);

        // Books (collectibles)
        this.drawBooks(cam);

        // Player
        this.drawPlayer(cam);

        // Company lock HUD indicator
        if (State.lockedRegion && !State.isInChallenge && !State.isInDialog) {
            const region = State.lockedRegion;
            const regionTheory = State.challenges.filter(c => c.region === region);
            const theoryDone = regionTheory.filter(c => State.player.completed_challenges.includes(c.id)).length;
            const theoryTotal = regionTheory.length;
            const allTheoryDone = theoryDone >= theoryTotal;

            // Background bar
            const barW = 320;
            const barH = 42;
            const barX = (this.W - barW) / 2;
            const barY = 8;

            ctx.save();
            ctx.fillStyle = 'rgba(15,23,42,0.92)';
            this._roundRect(ctx, barX, barY, barW, barH, 8);
            ctx.fill();
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            this._roundRect(ctx, barX, barY, barW, barH, 8);
            ctx.stroke();

            // Company name
            ctx.fillStyle = '#f8fafc';
            ctx.font = 'bold 11px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText('DENTRO: ' + region, barX + barW / 2, barY + 14);

            // Progress dots for theory questions
            const dotY = barY + 28;
            const dotSpacing = 22;
            const totalDots = theoryTotal + 1; // +1 for IDE
            const dotsStartX = barX + barW / 2 - (totalDots * dotSpacing) / 2;

            for (let i = 0; i < theoryTotal; i++) {
                const dotX = dotsStartX + i * dotSpacing + dotSpacing / 2;
                ctx.beginPath();
                ctx.arc(dotX, dotY, 6, 0, Math.PI * 2);
                if (i < theoryDone) {
                    ctx.fillStyle = '#22c55e'; // completed
                } else {
                    ctx.fillStyle = '#475569'; // pending
                }
                ctx.fill();
                ctx.fillStyle = '#f8fafc';
                ctx.font = '8px monospace';
                ctx.fillText('T' + (i + 1), dotX - 5, dotY + 3);
            }

            // IDE dot
            const ideDotX = dotsStartX + theoryTotal * dotSpacing + dotSpacing / 2;
            ctx.beginPath();
            ctx.arc(ideDotX, dotY, 6, 0, Math.PI * 2);
            ctx.fillStyle = allTheoryDone ? '#3b82f6' : '#475569';
            ctx.fill();
            ctx.fillStyle = '#f8fafc';
            ctx.font = '8px monospace';
            ctx.fillText('IDE', ideDotX - 8, dotY + 3);

            ctx.textAlign = 'left';
            ctx.restore();
        }

        // Door enter animation overlay
        if (State.enteringDoor && State.doorAnimProgress > 0) {
            const alpha = State.doorAnimProgress * 0.5;
            ctx.fillStyle = 'rgba(0,0,0,' + alpha + ')';
            ctx.fillRect(0, 0, this.W, this.H);

            if (State.doorAnimProgress > 0.5) {
                ctx.fillStyle = 'rgba(255,255,255,' + ((State.doorAnimProgress - 0.5) * 2) + ')';
                ctx.font = 'bold 20px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('Entrando na empresa...', this.W / 2, this.H / 2);
                ctx.textAlign = 'left';
            }
        }

        // Ground bottom fill
        ctx.fillStyle = '#7c5e3c';
        ctx.fillRect(0, this.GROUND_Y + 4, this.W, this.H);
    },

    _roundRect(ctx, x, y, w, h, r) {
        if (r < 0) r = 0;
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    },

    // --- Company logo vector draw functions ---
    // Convention: _draw_<customDraw key>(ctx, cx, cy, logoR, color)

    _draw_apple(ctx, cx, cy, logoR, color) {
        const s = logoR * 0.72;
        ctx.save();
        ctx.translate(cx, cy + s * 0.08);
        ctx.scale(s / 14, s / 14);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(0, -10);
        ctx.bezierCurveTo(3, -12, 8, -12, 10, -8);
        ctx.bezierCurveTo(12, -4, 12, 2, 10, 6);
        ctx.bezierCurveTo(8, 10, 5, 14, 0, 14);
        ctx.bezierCurveTo(-5, 14, -8, 10, -10, 6);
        ctx.bezierCurveTo(-12, 2, -12, -4, -10, -8);
        ctx.bezierCurveTo(-8, -12, -3, -12, 0, -10);
        ctx.closePath();
        ctx.fill();
        ctx.globalCompositeOperation = 'destination-out';
        ctx.beginPath();
        ctx.arc(12, -4, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalCompositeOperation = 'source-over';
        ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(0, -10); ctx.quadraticCurveTo(1, -15, 2, -16); ctx.stroke();
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.moveTo(2, -15); ctx.quadraticCurveTo(6, -17, 8, -14); ctx.quadraticCurveTo(6, -13, 2, -15); ctx.closePath(); ctx.fill();
        ctx.restore();
    },

    _draw_microsoft(ctx, cx, cy, logoR) {
        const s = logoR * 0.65;
        ctx.save();
        const gap = s * 0.12;
        const pane = s - gap / 2;
        ctx.fillStyle = '#f25022'; ctx.fillRect(cx - s, cy - s, pane, pane);
        ctx.fillStyle = '#7fba00'; ctx.fillRect(cx + gap / 2, cy - s, pane, pane);
        ctx.fillStyle = '#00a4ef'; ctx.fillRect(cx - s, cy + gap / 2, pane, pane);
        ctx.fillStyle = '#ffb900'; ctx.fillRect(cx + gap / 2, cy + gap / 2, pane, pane);
        ctx.restore();
    },

    _draw_disney(ctx, cx, cy, logoR, color) {
        const s = logoR * 0.72;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.scale(s / 14, s / 14);
        ctx.fillStyle = color;
        ctx.fillRect(-10, 2, 20, 6); ctx.fillRect(-8, -1, 16, 4);
        ctx.fillRect(-9, -4, 3, 6); ctx.fillRect(-4, -6, 3, 8); ctx.fillRect(1, -6, 3, 8); ctx.fillRect(6, -4, 3, 6);
        ctx.beginPath(); ctx.moveTo(-7.5, -8); ctx.lineTo(-9.5, -4); ctx.lineTo(-5.5, -4); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(-2.5, -11); ctx.lineTo(-4.5, -6); ctx.lineTo(-0.5, -6); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(2.5, -11); ctx.lineTo(0.5, -6); ctx.lineTo(4.5, -6); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(7.5, -8); ctx.lineTo(5.5, -4); ctx.lineTo(9.5, -4); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(0, -14); ctx.lineTo(-2, -6); ctx.lineTo(2, -6); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = color; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(0, 2, 13, Math.PI, 0, false); ctx.stroke();
        ctx.fillStyle = '#0f172a';
        ctx.beginPath(); ctx.arc(0, 8, 2.5, Math.PI, 0, true); ctx.fillRect(-2.5, 5.5, 5, 2.5); ctx.fill();
        ctx.restore();
    },

    _draw_google(ctx, cx, cy, logoR) {
        // Multicolored "G" - blue arc, red arc, yellow arc, green bar
        const s = logoR * 0.6;
        ctx.save();
        ctx.lineWidth = s * 0.38;
        ctx.lineCap = 'butt';
        // Blue top arc
        ctx.strokeStyle = '#4285f4';
        ctx.beginPath(); ctx.arc(cx, cy, s, -0.9, 0.6, true); ctx.stroke();
        // Red bottom-left arc
        ctx.strokeStyle = '#ea4335';
        ctx.beginPath(); ctx.arc(cx, cy, s, 0.6, 1.5); ctx.stroke();
        // Yellow bottom arc
        ctx.strokeStyle = '#fbbc05';
        ctx.beginPath(); ctx.arc(cx, cy, s, 1.5, 2.5); ctx.stroke();
        // Green right arc
        ctx.strokeStyle = '#34a853';
        ctx.beginPath(); ctx.arc(cx, cy, s, 2.5, 3.1); ctx.stroke();
        // Blue horizontal bar
        ctx.fillStyle = '#4285f4';
        ctx.fillRect(cx - s * 0.1, cy - s * 0.19, s * 1.1, s * 0.38);
        ctx.restore();
    },

    _draw_amazon(ctx, cx, cy, logoR, color) {
        // "a" text + orange smile arrow
        const s = logoR * 0.7;
        ctx.save();
        ctx.fillStyle = '#111';
        ctx.font = 'bold ' + Math.round(s * 1.6) + 'px sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('a', cx - s * 0.1, cy - s * 0.15);
        // Orange smile arrow from a to z
        ctx.strokeStyle = '#ff9900'; ctx.lineWidth = s * 0.2; ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cx - s * 0.8, cy + s * 0.5);
        ctx.quadraticCurveTo(cx, cy + s * 1.0, cx + s * 0.8, cy + s * 0.3);
        ctx.stroke();
        // Arrowhead
        ctx.fillStyle = '#ff9900';
        ctx.beginPath();
        ctx.moveTo(cx + s * 0.8, cy + s * 0.3);
        ctx.lineTo(cx + s * 0.5, cy + s * 0.55);
        ctx.lineTo(cx + s * 0.75, cy + s * 0.6);
        ctx.closePath(); ctx.fill();
        ctx.restore();
    },

    _draw_mercadolivre(ctx, cx, cy, logoR) {
        // Handshake inside circle (yellow bg, blue outline)
        const r = logoR * 0.85;
        ctx.save();
        // Yellow circle fill
        ctx.fillStyle = '#ffe600';
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
        // Blue outline
        ctx.strokeStyle = '#2d3277'; ctx.lineWidth = r * 0.15;
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
        // Handshake (two arcs meeting)
        ctx.strokeStyle = '#2d3277'; ctx.lineWidth = r * 0.14; ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cx - r * 0.55, cy + r * 0.1);
        ctx.quadraticCurveTo(cx - r * 0.1, cy - r * 0.4, cx, cy - r * 0.05);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(cx + r * 0.55, cy + r * 0.1);
        ctx.quadraticCurveTo(cx + r * 0.1, cy - r * 0.4, cx, cy - r * 0.05);
        ctx.stroke();
        // Fingers (small bumps)
        for (let i = -1; i <= 1; i++) {
            ctx.fillStyle = '#2d3277';
            ctx.beginPath();
            ctx.arc(cx + i * r * 0.2, cy - r * 0.25, r * 0.08, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    },

    _draw_paypal(ctx, cx, cy, logoR) {
        // Two overlapping "P" letters -- dark blue behind, light blue front
        const s = logoR * 0.75;
        const fs = Math.round(s * 2.2);
        ctx.save();
        ctx.font = 'bold ' + fs + 'px sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        // Back P (dark blue)
        ctx.fillStyle = '#003087';
        ctx.fillText('P', cx + s * 0.18, cy + s * 0.08);
        // Front P (light blue)
        ctx.fillStyle = '#009cde';
        ctx.fillText('P', cx - s * 0.18, cy - s * 0.08);
        ctx.restore();
    },

    _draw_spacex(ctx, cx, cy, logoR) {
        // Stylized "X" with arc swoosh
        const s = logoR * 0.7;
        ctx.save();
        ctx.fillStyle = '#111';
        ctx.font = 'bold ' + Math.round(s * 2.0) + 'px sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('X', cx, cy);
        // Swoosh arc across
        ctx.strokeStyle = '#111'; ctx.lineWidth = s * 0.12; ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cx - s * 1.0, cy + s * 0.1);
        ctx.quadraticCurveTo(cx, cy - s * 0.6, cx + s * 1.0, cy - s * 0.3);
        ctx.stroke();
        ctx.restore();
    },

    _draw_itau(ctx, cx, cy, logoR) {
        // Rounded orange square with white "itau" text
        const s = logoR * 0.82;
        ctx.save();
        // Orange rounded rect
        ctx.fillStyle = '#ec7000';
        const r = s * 0.3;
        ctx.beginPath();
        ctx.moveTo(cx - s + r, cy - s);
        ctx.lineTo(cx + s - r, cy - s);
        ctx.quadraticCurveTo(cx + s, cy - s, cx + s, cy - s + r);
        ctx.lineTo(cx + s, cy + s - r);
        ctx.quadraticCurveTo(cx + s, cy + s, cx + s - r, cy + s);
        ctx.lineTo(cx - s + r, cy + s);
        ctx.quadraticCurveTo(cx - s, cy + s, cx - s, cy + s - r);
        ctx.lineTo(cx - s, cy - s + r);
        ctx.quadraticCurveTo(cx - s, cy - s, cx - s + r, cy - s);
        ctx.closePath(); ctx.fill();
        // White inner rounded rect
        ctx.fillStyle = '#fff';
        const s2 = s * 0.72;
        const r2 = s2 * 0.35;
        ctx.beginPath();
        ctx.moveTo(cx - s2 + r2, cy - s2);
        ctx.lineTo(cx + s2 - r2, cy - s2);
        ctx.quadraticCurveTo(cx + s2, cy - s2, cx + s2, cy - s2 + r2);
        ctx.lineTo(cx + s2, cy + s2 - r2);
        ctx.quadraticCurveTo(cx + s2, cy + s2, cx + s2 - r2, cy + s2);
        ctx.lineTo(cx - s2 + r2, cy + s2);
        ctx.quadraticCurveTo(cx - s2, cy + s2, cx - s2, cy + s2 - r2);
        ctx.lineTo(cx - s2, cy - s2 + r2);
        ctx.quadraticCurveTo(cx - s2, cy - s2, cx - s2 + r2, cy - s2);
        ctx.closePath(); ctx.fill();
        // Orange "itau" text
        ctx.fillStyle = '#ec7000';
        ctx.font = 'bold ' + Math.round(s * 0.85) + 'px sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('ita\u00fa', cx, cy + s * 0.05);
        ctx.restore();
    },

    _draw_aurora_labs(ctx, cx, cy, logoR) {
        // Aurora Labs hexagonal flower/knot
        const s = logoR * 0.7;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.strokeStyle = '#111'; ctx.lineWidth = s * 0.22; ctx.lineCap = 'round';
        // 6 petal arcs arranged in a hexagonal pattern
        for (let i = 0; i < 6; i++) {
            ctx.save();
            ctx.rotate(i * Math.PI / 3);
            ctx.beginPath();
            ctx.moveTo(0, -s * 0.95);
            ctx.lineTo(0, -s * 0.3);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(s * 0.45, -s * 0.2, s * 0.55, Math.PI * 0.83, Math.PI * 1.35);
            ctx.stroke();
            ctx.restore();
        }
        ctx.restore();
    },

    drawPlayer(cam) {
        const p = this.player;
        const sx = p.x - cam;
        const sy = this.GROUND_Y - p.h + p.y;

        const drawH = p.h;
        const drawY = sy;

        // Body color based on state (camiseta preta)
        const bodyColors = {
            idle: '#1a1a1a',
            walk: '#1a1a1a',
            run: '#111111',
            jump: '#222222',
            fall: '#222222',
        };

        const headColor = this.getSkinColor(p.skinIndex);
        const bodyColor = bodyColors[p.state] || '#3b82f6';
        const isFlipped = p.facing === -1;

        ctx = this.ctx;
        ctx.save();
        if (isFlipped) {
            ctx.translate(sx + p.w, 0);
            ctx.scale(-1, 1);
            ctx.translate(0, 0);
        } else {
            ctx.translate(sx, 0);
        }

        // Shadow (smaller when jumping)
        const shadowScale = p.onGround ? 1 : Math.max(0.3, 1 + p.y * 0.003);
        ctx.fillStyle = `rgba(0,0,0,${0.15 * shadowScale})`;
        ctx.beginPath();
        ctx.ellipse(p.w / 2, this.GROUND_Y + 2, 22 * shadowScale, 6 * shadowScale, 0, 0, Math.PI * 2);
        ctx.fill();

        // Animation time
        const t = performance.now();

        // Leg animation offsets -- smooth sinusoidal gait
        let legLAngle = 0, legRAngle = 0;
        if (p.state === 'walk') {
            const cycle = Math.sin(t * 0.012);
            legLAngle = cycle * 14;
            legRAngle = -cycle * 14;
        } else if (p.state === 'run') {
            const cycle = Math.sin(t * 0.02);
            legLAngle = cycle * 22;
            legRAngle = -cycle * 22;
        } else if (p.state === 'jump') {
            legLAngle = -12; legRAngle = 8;
        } else if (p.state === 'fall') {
            legLAngle = 6; legRAngle = -6;
        }

        // Legs (calca jeans) -- drawn as angled rectangles
        ctx.fillStyle = '#4472C4';
        ctx.save();
        ctx.translate(p.w * 0.30, drawY + drawH * 0.65);
        ctx.rotate(legLAngle * Math.PI / 180);
        ctx.fillRect(-4, 0, 9, drawH * 0.33);
        // Shoe left
        ctx.fillStyle = '#e5e7eb';
        this.roundRect(ctx, -5, drawH * 0.33 - 2, 12, 8, 3);
        ctx.fill();
        // Shoe sole
        ctx.fillStyle = '#555';
        ctx.fillRect(-5, drawH * 0.33 + 4, 12, 3);
        ctx.restore();

        ctx.fillStyle = '#4472C4';
        ctx.save();
        ctx.translate(p.w * 0.60, drawY + drawH * 0.65);
        ctx.rotate(legRAngle * Math.PI / 180);
        ctx.fillRect(-4, 0, 9, drawH * 0.33);
        // Shoe right
        ctx.fillStyle = '#e5e7eb';
        this.roundRect(ctx, -5, drawH * 0.33 - 2, 12, 8, 3);
        ctx.fill();
        ctx.fillStyle = '#555';
        ctx.fillRect(-5, drawH * 0.33 + 4, 12, 3);
        ctx.restore();

        // Body (torso) -- camiseta preta
        const torsoY = drawY + drawH * 0.2;
        const torsoH = drawH * 0.45;
        ctx.fillStyle = bodyColor;
        this.roundRect(ctx, p.w * 0.15, torsoY, p.w * 0.7, torsoH, 6);
        ctx.fill();

        // Collar detail
        ctx.fillStyle = '#333';
        ctx.beginPath();
        ctx.arc(p.w / 2, torsoY + 2, 8, 0, Math.PI);
        ctx.fill();

        // Shirt text 'Garage'
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 6px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Garage', p.w / 2, torsoY + torsoH * 0.45);

        // Arms -- swing opposite to legs for natural motion
        let armLAngle = 0, armRAngle = 0;
        if (p.state === 'walk') {
            armLAngle = -Math.sin(t * 0.012) * 20;
            armRAngle = Math.sin(t * 0.012) * 20;
        } else if (p.state === 'run') {
            armLAngle = -Math.sin(t * 0.02) * 35;
            armRAngle = Math.sin(t * 0.02) * 35;
        } else if (p.state === 'jump') {
            armLAngle = -40; armRAngle = -40; // arms up
        } else if (p.state === 'fall') {
            armLAngle = 25; armRAngle = 25;
        }

        // Left arm (skin + sleeve)
        ctx.save();
        ctx.translate(p.w * 0.10, torsoY + 4);
        ctx.rotate(armLAngle * Math.PI / 180);
        ctx.fillStyle = bodyColor; // sleeve
        ctx.fillRect(-4, 0, 9, 14);
        ctx.fillStyle = headColor; // skin forearm
        ctx.fillRect(-3, 14, 7, torsoH * 0.4);
        ctx.restore();

        // Right arm
        ctx.save();
        ctx.translate(p.w * 0.80, torsoY + 4);
        ctx.rotate(armRAngle * Math.PI / 180);
        ctx.fillStyle = bodyColor;
        ctx.fillRect(-4, 0, 9, 14);
        ctx.fillStyle = headColor;
        ctx.fillRect(-3, 14, 7, torsoH * 0.4);
        ctx.restore();

        // Head
        const headSize = p.w * 0.55;
        const headX = p.w / 2;
        const headY = drawY + headSize * 0.5 + 2;
        ctx.fillStyle = headColor;
        ctx.beginPath();
        ctx.arc(headX, headY, headSize / 2, 0, Math.PI * 2);
        ctx.fill();

        // Hair
        ctx.fillStyle = '#1a1a2e';
        ctx.beginPath();
        ctx.arc(headX, headY - 4, headSize / 2 + 1, Math.PI, Math.PI * 2);
        ctx.fill();

        // Longer hair for female avatars (index 2, 3)
        if (p.skinIndex >= 2) {
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(p.w * 0.12, headY - 2, 6, drawH * 0.35);
            ctx.fillRect(p.w * 0.72, headY - 2, 6, drawH * 0.35);
        }

        // Eyes
        const eyeY = headY + 2;
        const blinkOpen = Math.sin(performance.now() * 0.003) > -0.95;
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.ellipse(headX - 7, eyeY, 5, blinkOpen ? 5 : 1, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(headX + 7, eyeY, 5, blinkOpen ? 5 : 1, 0, 0, Math.PI * 2);
        ctx.fill();

        // Pupils (look in facing direction)
        ctx.fillStyle = '#111';
        ctx.beginPath();
        ctx.arc(headX - 5, eyeY + 1, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(headX + 9, eyeY + 1, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Mouth
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        if (p.state === 'jump' || p.state === 'fall') {
            // Open mouth (surprise)
            ctx.arc(headX, headY + 10, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#333';
            ctx.fill();
        } else {
            // Smile
            ctx.arc(headX, headY + 7, 5, 0.1 * Math.PI, 0.9 * Math.PI);
            ctx.stroke();
        }

        ctx.restore();
    },

    getSkinColor(idx) {
        const colors = ['#F5D0A9', '#8B6F47', '#F5D0A9', '#8B6F47'];
        return colors[idx % colors.length] || colors[0];
    },

    drawNPCs(cam) {
        const ctx = this.ctx;
        const time = performance.now() * 0.001;

        NPC_DATA.forEach(npc => {
            const sx = npc.worldX - cam;
            if (sx < -80 || sx > this.W + 80) return;

            const bobY = Math.sin(time * 2 + npc.worldX * 0.01) * 3;
            const ny = this.GROUND_Y - 90 + bobY;
            const L = npc.look || {};
            const skin = L.skinTone || this.getSkinColor(npc.skin);

            // Shadow
            ctx.fillStyle = 'rgba(0,0,0,0.15)';
            ctx.beginPath();
            ctx.ellipse(sx, this.GROUND_Y + 2, 25, 7, 0, 0, Math.PI * 2);
            ctx.fill();

            // Legs
            ctx.fillStyle = L.pants || '#333';
            const legSwing = Math.sin(time * 1.2 + npc.worldX) * 2;
            ctx.fillRect(sx - 8, ny + 60 + legSwing, 7, 28 - legSwing);
            ctx.fillRect(sx + 2, ny + 60 - legSwing, 7, 28 + legSwing);

            // Shoes
            ctx.fillStyle = '#333';
            ctx.fillRect(sx - 10, this.GROUND_Y - 6, 11, 6);
            ctx.fillRect(sx + 1, this.GROUND_Y - 6, 11, 6);

            // Body / Torso
            const shirtColor = L.shirt || '#666';
            if (L.suit) {
                // Suit jacket
                ctx.fillStyle = L.suit;
                this.roundRect(ctx, sx - 20, ny + 14, 40, 50, 6);
                ctx.fill();
                // Shirt underneath
                ctx.fillStyle = '#eee';
                ctx.fillRect(sx - 6, ny + 18, 12, 20);
            } else if (L.hoodie) {
                // Hoodie (Zuckerberg)
                ctx.fillStyle = L.hoodie;
                this.roundRect(ctx, sx - 20, ny + 14, 40, 50, 6);
                ctx.fill();
                // Hood line
                ctx.strokeStyle = '#333';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(sx, ny + 14, 12, Math.PI, 0);
                ctx.stroke();
                // Hoodie strings
                ctx.strokeStyle = '#aaa';
                ctx.lineWidth = 1;
                ctx.beginPath(); ctx.moveTo(sx - 4, ny + 20); ctx.lineTo(sx - 4, ny + 35); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(sx + 4, ny + 20); ctx.lineTo(sx + 4, ny + 35); ctx.stroke();
            } else if (L.turtleneck) {
                // Steve Jobs black turtleneck
                ctx.fillStyle = '#111';
                this.roundRect(ctx, sx - 18, ny + 14, 36, 50, 6);
                ctx.fill();
            } else if (L.jacket) {
                // Jacket (Elon)
                ctx.fillStyle = L.jacket;
                this.roundRect(ctx, sx - 20, ny + 14, 40, 50, 6);
                ctx.fill();
                // Shirt visible
                ctx.fillStyle = '#ddd';
                ctx.fillRect(sx - 5, ny + 18, 10, 15);
            } else {
                // Default shirt
                ctx.fillStyle = shirtColor;
                this.roundRect(ctx, sx - 18, ny + 14, 36, 50, 6);
                ctx.fill();
            }

            // Tie (Bill Gates)
            if (L.tie) {
                ctx.fillStyle = L.tie;
                ctx.beginPath();
                ctx.moveTo(sx - 3, ny + 20);
                ctx.lineTo(sx + 3, ny + 20);
                ctx.lineTo(sx + 2, ny + 45);
                ctx.lineTo(sx, ny + 50);
                ctx.lineTo(sx - 2, ny + 45);
                ctx.closePath();
                ctx.fill();
            }

            // Arms
            const armB = Math.sin(time * 1.5 + npc.worldX) * 3;
            ctx.fillStyle = skin;
            ctx.fillRect(sx - 24, ny + 20 + armB, 8, 28);
            ctx.fillRect(sx + 16, ny + 20 - armB, 8, 28);

            // Sleeves match body
            ctx.fillStyle = L.suit || L.hoodie || L.jacket || (L.turtleneck ? '#111' : shirtColor);
            ctx.fillRect(sx - 24, ny + 18 + armB, 8, 12);
            ctx.fillRect(sx + 16, ny + 18 - armB, 8, 12);

            // Head
            ctx.fillStyle = skin;
            ctx.beginPath();
            ctx.arc(sx, ny + 8, 16, 0, Math.PI * 2);
            ctx.fill();

            // Turtleneck collar (sits at base of neck, below chin)
            if (L.turtleneck) {
                ctx.fillStyle = '#1a1a1a';
                this.roundRect(ctx, sx - 10, ny + 21, 20, 5, 2);
                ctx.fill();
            }

            // Hair
            if (L.hairStyle === 'bald' || L.bald) {
                // Bald (Bezos) - just a slight skin shine
                ctx.fillStyle = 'rgba(255,255,255,0.08)';
                ctx.beginPath();
                ctx.arc(sx - 4, ny - 2, 8, 0, Math.PI * 2);
                ctx.fill();
            } else if (L.hairStyle === 'bald-sides') {
                // Bald top with sides (Geschke)
                ctx.fillStyle = L.hair || '#ccc';
                ctx.fillRect(sx - 16, ny + 2, 8, 12);
                ctx.fillRect(sx + 8, ny + 2, 8, 12);
            } else if (L.hairStyle === 'parted') {
                // Side-parted hair (Gates)
                ctx.fillStyle = L.hair || '#8B6F47';
                ctx.beginPath();
                ctx.arc(sx, ny + 4, 16, Math.PI + 0.3, Math.PI * 2 + 0.1);
                ctx.fill();
                // Parting line
                ctx.fillRect(sx - 14, ny - 6, 28, 6);
            } else if (L.hairStyle === 'curly') {
                // Curly (Larry/Sergey)
                ctx.fillStyle = L.hair || '#333';
                ctx.beginPath();
                ctx.arc(sx, ny + 2, 17, Math.PI, Math.PI * 2);
                ctx.fill();
                // Curly bumps
                for (let i = -2; i <= 2; i++) {
                    ctx.beginPath();
                    ctx.arc(sx + i * 6, ny - 8, 5, 0, Math.PI * 2);
                    ctx.fill();
                }
            } else if (L.hairStyle === 'curly-short') {
                // Short curly (Zuckerberg)
                ctx.fillStyle = L.hair || '#8B6F47';
                ctx.beginPath();
                ctx.arc(sx, ny + 4, 16, Math.PI + 0.2, Math.PI * 2 - 0.2);
                ctx.fill();
                ctx.fillRect(sx - 12, ny - 6, 24, 5);
            } else {
                // Short hair (default - Jobs, Musk, Thiel, Torvalds)
                ctx.fillStyle = L.hair || '#222';
                ctx.beginPath();
                ctx.arc(sx, ny + 4, 16, Math.PI, Math.PI * 2);
                ctx.fill();
                ctx.fillRect(sx - 14, ny - 4, 28, 5);
            }

            // Beard (symmetric jaw-line)
            if (L.beard) {
                ctx.fillStyle = L.beard;
                ctx.beginPath();
                ctx.moveTo(sx - 9, ny + 12);
                ctx.quadraticCurveTo(sx - 10, ny + 20, sx, ny + 23);
                ctx.quadraticCurveTo(sx + 10, ny + 20, sx + 9, ny + 12);
                ctx.closePath();
                ctx.fill();
            }

            // Glasses
            if (L.glasses) {
                ctx.strokeStyle = '#333';
                ctx.lineWidth = 1.5;
                if (L.glassesStyle === 'round') {
                    // Round glasses (Jobs, Geschke, Torvalds)
                    ctx.beginPath(); ctx.arc(sx - 6, ny + 8, 5, 0, Math.PI * 2); ctx.stroke();
                    ctx.beginPath(); ctx.arc(sx + 6, ny + 8, 5, 0, Math.PI * 2); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(sx - 1, ny + 8); ctx.lineTo(sx + 1, ny + 8); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(sx - 11, ny + 8); ctx.lineTo(sx - 15, ny + 6); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(sx + 11, ny + 8); ctx.lineTo(sx + 15, ny + 6); ctx.stroke();
                } else {
                    // Square glasses (Gates)
                    ctx.strokeRect(sx - 11, ny + 5, 9, 7);
                    ctx.strokeRect(sx + 2, ny + 5, 9, 7);
                    ctx.beginPath(); ctx.moveTo(sx - 2, ny + 8); ctx.lineTo(sx + 2, ny + 8); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(sx - 11, ny + 8); ctx.lineTo(sx - 15, ny + 6); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(sx + 11, ny + 8); ctx.lineTo(sx + 15, ny + 6); ctx.stroke();
                }
            }

            // Eyes
            ctx.fillStyle = '#fff';
            ctx.beginPath(); ctx.arc(sx - 5, ny + 8, 3.5, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(sx + 5, ny + 8, 3.5, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#111';
            ctx.beginPath(); ctx.arc(sx - 4, ny + 9, 1.8, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(sx + 4, ny + 9, 1.8, 0, Math.PI * 2); ctx.fill();

            // Mouth - slight smile
            ctx.strokeStyle = '#555';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.arc(sx, ny + 14, 4, 0.15 * Math.PI, 0.85 * Math.PI);
            ctx.stroke();

            // Name tag
            const stageColor = npc.stage === 'Principal' || npc.stage === 'Staff' ? '#fbbf24' : '#fff';
            ctx.fillStyle = 'rgba(0,0,0,0.75)';
            ctx.font = 'bold 11px "JetBrains Mono", monospace';
            const nameW = ctx.measureText(npc.name).width + 16;
            this.roundRect(ctx, sx - nameW / 2, ny - 28, nameW, 22, 4);
            ctx.fill();
            ctx.fillStyle = stageColor;
            ctx.textAlign = 'center';
            ctx.fillText(npc.name, sx, ny - 12);

            // Speech bubble if interactable
            if (State.interactionTarget && State.interactionTarget.id === npc.id) {
                const pulse = Math.sin(Date.now() * 0.005) * 2;
                const bx = sx;
                const by = ny - 46 + pulse;

                // Bubble background
                ctx.fillStyle = '#fff';
                this.roundRect(ctx, bx - 18, by - 10, 36, 20, 6);
                ctx.fill();
                ctx.strokeStyle = '#374151';
                ctx.lineWidth = 1.5;
                this.roundRect(ctx, bx - 18, by - 10, 36, 20, 6);
                ctx.stroke();

                // Bubble tail (triangle pointing down)
                ctx.fillStyle = '#fff';
                ctx.beginPath();
                ctx.moveTo(bx - 4, by + 10);
                ctx.lineTo(bx + 4, by + 10);
                ctx.lineTo(bx, by + 16);
                ctx.closePath();
                ctx.fill();
                ctx.strokeStyle = '#374151';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(bx - 4, by + 10);
                ctx.lineTo(bx, by + 16);
                ctx.lineTo(bx + 4, by + 10);
                ctx.stroke();

                // Three dots animation (typing indicator)
                const dotBase = Date.now() * 0.004;
                for (let i = 0; i < 3; i++) {
                    const dotY = by + Math.sin(dotBase + i * 1.2) * 2;
                    ctx.fillStyle = '#374151';
                    ctx.beginPath();
                    ctx.arc(bx - 6 + i * 6, dotY, 2.2, 0, Math.PI * 2);
                    ctx.fill();
                }
            }

            ctx.textAlign = 'left';
        });
    },

    drawBooks(cam) {
        const ctx = this.ctx;
        const time = performance.now() * 0.001;

        BOOKS_DATA.forEach(book => {
            if (State.collectedBooks.includes(book.id)) return;

            const sx = book.worldX - cam;
            if (sx < -60 || sx > this.W + 60) return;

            const bobY = Math.sin(time * 2.5 + book.worldX * 0.02) * 8;
            const rot = Math.sin(time * 1.5 + book.worldX * 0.03) * 0.06;
            const by = this.GROUND_Y - book.floatY + bobY;

            ctx.save();
            ctx.translate(sx, by);
            ctx.rotate(rot);

            // Outer glow
            const glowAlpha = 0.12 + Math.sin(time * 3 + book.worldX) * 0.06;
            ctx.shadowColor = book.color;
            ctx.shadowBlur = 18 + Math.sin(time * 4) * 6;

            // Book dimensions
            const bw = 40, bh = 52, spine = 8;

            // Back cover (darker shade)
            ctx.fillStyle = this._darkenColor(book.color, 0.6);
            this.roundRect(ctx, -bw / 2 + 3, -bh / 2 + 2, bw, bh, 3);
            ctx.fill();

            // Spine
            ctx.shadowBlur = 0;
            ctx.fillStyle = this._darkenColor(book.color, 0.4);
            ctx.fillRect(-bw / 2, -bh / 2, spine, bh);
            // Spine ridges
            ctx.strokeStyle = 'rgba(0,0,0,0.2)';
            ctx.lineWidth = 0.5;
            for (let r = 0; r < 4; r++) {
                const ry = -bh / 2 + 8 + r * 12;
                ctx.beginPath();
                ctx.moveTo(-bw / 2 + 1, ry);
                ctx.lineTo(-bw / 2 + spine - 1, ry);
                ctx.stroke();
            }

            // Front cover
            ctx.fillStyle = book.color;
            this.roundRect(ctx, -bw / 2 + spine, -bh / 2, bw - spine, bh, 3);
            ctx.fill();

            // Cover border
            ctx.strokeStyle = 'rgba(255,255,255,0.3)';
            ctx.lineWidth = 1;
            this.roundRect(ctx, -bw / 2 + spine + 2, -bh / 2 + 2, bw - spine - 4, bh - 4, 2);
            ctx.stroke();

            // Cover decoration -- horizontal lines
            ctx.strokeStyle = 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(-bw / 2 + spine + 4, -bh / 2 + 6);
            ctx.lineTo(bw / 2 - 4, -bh / 2 + 6);
            ctx.moveTo(-bw / 2 + spine + 4, bh / 2 - 6);
            ctx.lineTo(bw / 2 - 4, bh / 2 - 6);
            ctx.stroke();

            // "< / >" symbol (tech icon)
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 11px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('</ >', spine / 2 + 2, -6);

            // "LIVRO DE" text
            ctx.font = '5px "JetBrains Mono", monospace';
            ctx.fillStyle = 'rgba(255,255,255,0.85)';
            ctx.fillText('LIVRO DE', spine / 2 + 2, 6);

            // "TECNOLOGIA" text
            ctx.font = 'bold 6px "JetBrains Mono", monospace';
            ctx.fillStyle = '#fbbf24';
            ctx.fillText('TECNOLOGIA', spine / 2 + 2, 14);

            // Pages visible on bottom edge
            ctx.fillStyle = '#fef9ef';
            ctx.fillRect(-bw / 2 + spine + 1, bh / 2 - 3, bw - spine - 2, 3);
            // Page lines
            ctx.strokeStyle = 'rgba(0,0,0,0.1)';
            ctx.lineWidth = 0.3;
            for (let p = 0; p < 3; p++) {
                ctx.beginPath();
                ctx.moveTo(-bw / 2 + spine + 1, bh / 2 - 3 + p);
                ctx.lineTo(bw / 2 - 1, bh / 2 - 3 + p);
                ctx.stroke();
            }

            // Bookmark ribbon
            ctx.fillStyle = '#ef4444';
            ctx.beginPath();
            ctx.moveTo(bw / 2 - 10, -bh / 2);
            ctx.lineTo(bw / 2 - 10, -bh / 2 - 10);
            ctx.lineTo(bw / 2 - 7, -bh / 2 - 6);
            ctx.lineTo(bw / 2 - 4, -bh / 2 - 10);
            ctx.lineTo(bw / 2 - 4, -bh / 2);
            ctx.closePath();
            ctx.fill();

            ctx.textAlign = 'left';
            ctx.textBaseline = 'alphabetic';

            // Sparkle particles
            ctx.shadowBlur = 0;
            ctx.shadowColor = 'transparent';
            const sparkle1 = Math.sin(time * 5 + book.worldX * 0.1);
            const sparkle2 = Math.cos(time * 7 + book.worldX * 0.15);
            if (sparkle1 > 0.6) {
                ctx.fillStyle = '#fbbf24';
                const sx2 = 24 + sparkle1 * 8;
                const sy2 = -10 + sparkle2 * 6;
                this._drawStar(ctx, sx2, sy2, 3, 1.2, 4);
            }
            if (sparkle2 > 0.5) {
                ctx.fillStyle = '#fff';
                const sx3 = -28 + sparkle2 * 6;
                const sy3 = 5 + sparkle1 * 8;
                this._drawStar(ctx, sx3, sy3, 2.5, 1, 4);
            }
            if (sparkle1 < -0.7) {
                ctx.fillStyle = '#a78bfa';
                this._drawStar(ctx, 18, 20 + sparkle2 * 4, 2, 0.8, 4);
            }

            ctx.restore();
        });
    },

    _darkenColor(hex, factor) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgb(${Math.floor(r * factor)},${Math.floor(g * factor)},${Math.floor(b * factor)})`;
    },

    _drawStar(ctx, cx, cy, outerR, innerR, points) {
        ctx.beginPath();
        for (let i = 0; i < points * 2; i++) {
            const r = i % 2 === 0 ? outerR : innerR;
            const a = (Math.PI / points) * i - Math.PI / 2;
            const method = i === 0 ? 'moveTo' : 'lineTo';
            ctx[method](cx + Math.cos(a) * r, cy + Math.sin(a) * r);
        }
        ctx.closePath();
        ctx.fill();
    },

    showBookPopup(book) {
        State.isBookPopup = true;
        document.getElementById('bookTitle').textContent = book.title;
        document.getElementById('bookAuthor').textContent = book.author;
        document.getElementById('bookSummary').textContent = book.summary;
        document.getElementById('bookLesson').textContent = 'Licao-chave: ' + book.lesson;
        document.getElementById('bookPopup').classList.add('visible');
    },

    closeBookPopup() {
        State.isBookPopup = false;
        document.getElementById('bookPopup').classList.remove('visible');
    },

    updateBookHUD() {
        const el = document.getElementById('hudBooks');
        if (el) el.textContent = State.collectedBooks.length + ' / ' + BOOKS_DATA.length;
    },

    roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    },

    /* --- GAME LOOP --- */
    start() {
        this.running = true;
        this.lastTime = performance.now();
        this._loop();
    },

    stop() { this.running = false; },

    _loop() {
        if (!this.running) return;
        requestAnimationFrame(() => this._loop());
        const now = performance.now();
        const dt = Math.min((now - this.lastTime) / 1000, 0.05);
        this.lastTime = now;
        if (!State.paused) this.update(dt);
        this.draw();
    },
};

// ---- UI ----
const UI = {
    showScreen(id) {
        if (typeof StudyChat !== 'undefined' && StudyChat.isOpen() && id !== 'screen-world') {
            StudyChat.close();
        }
        if (typeof Learning !== 'undefined' && Learning.isOpen() && id !== 'screen-world') {
            Learning.cancel();
        }
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        const el = document.getElementById(id);
        if (el) el.classList.add('active');
        if (id === 'screen-world') { World.start(); SFX.playMusic('explore'); }
        else { World.stop(); if (id === 'screen-title' || id === 'screen-onboarding') SFX.playMusic('title'); }
        if (id === 'screen-onboarding') this._drawOnboardingChar();
        if (id === 'screen-title') this.updateTitleButtons();
    },

    updateTitleButtons() {
        const continueBtn = document.getElementById('btnContinueGame');
        if (continueBtn) {
            continueBtn.style.display = Auth.hasSession() ? '' : 'none';
        }
        // Show admin dashboard link for users with admin role on JWT
        const adminBtn = document.getElementById('btnAdminDash');
        if (adminBtn) {
            adminBtn.style.display = Auth.isAdmin() ? '' : 'none';
        }
    },

    _drawOnboardingChar() {
        // Start animation loop for avatar preview (stops when screen changes)
        if (this._onboardingAnimId) cancelAnimationFrame(this._onboardingAnimId);
        const self = this;
        (function loop() {
            const screen = document.getElementById('screen-onboarding');
            if (!screen || !screen.classList.contains('active')) {
                self._onboardingAnimId = null;
                return;
            }
            try {
                self._drawAnimatedAvatar('onboardingCharBoy', 'male');
                self._drawAnimatedAvatar('onboardingCharGirl', 'female');
            } catch (e) {
                console.error('[GARAGE] Avatar render error:', e);
            }
            self._onboardingAnimId = requestAnimationFrame(loop);
        })();
    },

    /** Helper: draw a rounded rectangle path (self-contained, no external deps). */
    _rrect(ctx, x, y, w, h, r) {
        if (r < 0) r = 0;
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    },

    /**
     * Draw an animated character preview on a small canvas.
     * Reuses the same visual style as World.drawPlayer (walk cycle).
     * Completely self-contained -- no dependency on World object.
     * @param {string} canvasId  - DOM id of the target canvas
     * @param {'male'|'female'} gender - controls hair style and accessories
     */
    _drawAnimatedAvatar(canvasId, gender) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);

        const t = performance.now();
        const skinColor = '#F5D0A9';
        const bodyColor = '#1a1a1a';
        const isFemale = gender === 'female';

        // Character dimensions (proportional to the in-game player)
        const pw = 48;   // player width reference
        const ph = 90;   // player height reference
        const ox = W / 2 - pw / 2;  // center horizontally
        const oy = H - ph - 18;     // stand near bottom

        ctx.save();
        ctx.translate(ox, oy);

        // ------ Shadow ------
        ctx.fillStyle = 'rgba(0,0,0,0.13)';
        ctx.beginPath();
        ctx.ellipse(pw / 2, ph + 2, 22, 6, 0, 0, Math.PI * 2);
        ctx.fill();

        // ------ Walk cycle (continuous) ------
        const cycle = Math.sin(t * 0.005);
        const legLAngle = cycle * 14;
        const legRAngle = -cycle * 14;
        const armLAngle = -cycle * 20;
        const armRAngle = cycle * 20;

        // ------ Legs (blue jeans) ------
        ctx.fillStyle = '#4472C4';
        // Left leg
        ctx.save();
        ctx.translate(pw * 0.30, ph * 0.65);
        ctx.rotate(legLAngle * Math.PI / 180);
        ctx.fillRect(-4, 0, 9, ph * 0.33);
        // Shoe left
        ctx.fillStyle = '#e5e7eb';
        this._rrect(ctx, -5, ph * 0.33 - 2, 12, 8, 3);
        ctx.fill();
        ctx.fillStyle = '#555';
        ctx.fillRect(-5, ph * 0.33 + 4, 12, 3);
        ctx.restore();

        // Right leg
        ctx.fillStyle = '#4472C4';
        ctx.save();
        ctx.translate(pw * 0.60, ph * 0.65);
        ctx.rotate(legRAngle * Math.PI / 180);
        ctx.fillRect(-4, 0, 9, ph * 0.33);
        ctx.fillStyle = '#e5e7eb';
        this._rrect(ctx, -5, ph * 0.33 - 2, 12, 8, 3);
        ctx.fill();
        ctx.fillStyle = '#555';
        ctx.fillRect(-5, ph * 0.33 + 4, 12, 3);
        ctx.restore();

        // ------ Torso (black tee) ------
        const torsoY = ph * 0.2;
        const torsoH = ph * 0.45;
        ctx.fillStyle = bodyColor;
        this._rrect(ctx, pw * 0.15, torsoY, pw * 0.7, torsoH, 6);
        ctx.fill();

        // Collar
        ctx.fillStyle = '#333';
        ctx.beginPath();
        ctx.arc(pw / 2, torsoY + 2, 8, 0, Math.PI);
        ctx.fill();

        // Shirt text
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 6px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Garage', pw / 2, torsoY + torsoH * 0.45);

        // ------ Arms ------
        // Left arm
        ctx.save();
        ctx.translate(pw * 0.10, torsoY + 4);
        ctx.rotate(armLAngle * Math.PI / 180);
        ctx.fillStyle = bodyColor;
        ctx.fillRect(-4, 0, 9, 14);
        ctx.fillStyle = skinColor;
        ctx.fillRect(-3, 14, 7, torsoH * 0.4);
        ctx.restore();

        // Right arm
        ctx.save();
        ctx.translate(pw * 0.80, torsoY + 4);
        ctx.rotate(armRAngle * Math.PI / 180);
        ctx.fillStyle = bodyColor;
        ctx.fillRect(-4, 0, 9, 14);
        ctx.fillStyle = skinColor;
        ctx.fillRect(-3, 14, 7, torsoH * 0.4);
        ctx.restore();

        // ------ Head ------
        const headSize = pw * 0.55;
        const headX = pw / 2;
        const headY = headSize * 0.5 + 2;

        // Female: long hair behind head (drawn before head circle)
        if (isFemale) {
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(pw * 0.12, headY - 2, 6, ph * 0.35);
            ctx.fillRect(pw * 0.72, headY - 2, 6, ph * 0.35);
        }

        ctx.fillStyle = skinColor;
        ctx.beginPath();
        ctx.arc(headX, headY, headSize / 2, 0, Math.PI * 2);
        ctx.fill();

        // Hair (top)
        ctx.fillStyle = '#1a1a2e';
        ctx.beginPath();
        ctx.arc(headX, headY - 4, headSize / 2 + 1, Math.PI, Math.PI * 2);
        ctx.fill();

        if (isFemale) {
            // Side hair strands
            ctx.fillRect(headX - headSize / 2 - 1, headY - 4, 5, 10);
            ctx.fillRect(headX + headSize / 2 - 4, headY - 4, 5, 10);
            // Fringe
            ctx.beginPath();
            ctx.moveTo(headX - 10, headY - headSize / 2 - 5);
            ctx.quadraticCurveTo(headX - 2, headY - headSize / 2 + 2, headX + 4, headY - headSize / 2 - 5);
            ctx.fill();
            // Hair bow
            ctx.fillStyle = '#f472b6';
            ctx.beginPath();
            ctx.arc(headX + headSize / 2 - 2, headY - headSize / 2 + 2, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#ec4899';
            ctx.beginPath();
            ctx.arc(headX + headSize / 2 - 2, headY - headSize / 2 + 2, 2, 0, Math.PI * 2);
            ctx.fill();
        } else {
            // Bowl cut side flaps
            ctx.fillRect(headX - headSize / 2 - 1, headY - 4, 4, 6);
            ctx.fillRect(headX + headSize / 2 - 3, headY - 4, 4, 6);
        }

        // ------ Eyes (with blink) ------
        const eyeY = headY + 2;
        const blinkOpen = Math.sin(t * 0.003) > -0.95;
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.ellipse(headX - 7, eyeY, 5, blinkOpen ? 5 : 1, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(headX + 7, eyeY, 5, blinkOpen ? 5 : 1, 0, 0, Math.PI * 2);
        ctx.fill();

        // Pupils
        ctx.fillStyle = '#111';
        ctx.beginPath();
        ctx.arc(headX - 5, eyeY + 1, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(headX + 9, eyeY + 1, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Female eyelashes
        if (isFemale) {
            ctx.strokeStyle = '#1a1a2e';
            ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.moveTo(headX - 12, eyeY - 3); ctx.lineTo(headX - 10, eyeY - 4); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(headX + 12, eyeY - 3); ctx.lineTo(headX + 10, eyeY - 4); ctx.stroke();
        }

        // ------ Mouth (smile) ------
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(headX, headY + 7, 5, 0.1 * Math.PI, 0.9 * Math.PI);
        ctx.stroke();

        ctx.restore();
    },

    selectAvatar(el) {
        const container = document.getElementById('avatarSelection');
        if (!container) return;
        container.querySelectorAll('.avatar-card').forEach(c => c.classList.remove('selected'));
        el.classList.add('selected');
        SFX.menuConfirm();
    },

    getSelectedAvatar() {
        const selected = document.querySelector('.avatar-card.selected');
        const isGirl = selected && selected.dataset.avatar === 'girl';
        return {
            index: isGirl ? 2 : 0,
            gender: isGirl ? 'female' : 'male',
            ethnicity: 'white'
        };
    },

    updateHUD(player) {
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'CEO' };
        document.getElementById('hudName').textContent = player.name || '---';
        document.getElementById('hudStage').textContent = STAGE_PT[player.stage] || player.stage || 'Estagiario';
        document.getElementById('hudScore').textContent = player.score || 0;
        document.getElementById('hudErrors').textContent = (player.current_errors || 0) + ' / 2';
        // Sync book counter
        const booksEl = document.getElementById('hudBooks');
        if (booksEl) booksEl.textContent = State.collectedBooks.length + ' / ' + BOOKS_DATA.length;
        // Sync company counter
        const compEl = document.getElementById('hudCompanies');
        if (compEl) compEl.textContent = State.completedRegions.length + ' / ' + BUILDINGS.length;
    },

    // --- Metrics Panel ---
    _metricsOpen: false,

    toggleMetrics() {
        this._metricsOpen = !this._metricsOpen;
        const el = document.getElementById('metricsOverlay');
        if (!el) return;
        if (this._metricsOpen) {
            this.populateMetrics();
            el.classList.add('visible');
        } else {
            el.classList.remove('visible');
        }
    },

    switchMetricsTab(tab) {
        document.querySelectorAll('.metrics-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });
        document.querySelectorAll('.metrics-tab-content').forEach(c => {
            c.classList.toggle('active', c.id === (tab === 'companies' ? 'metricsCompanies' : 'metricsBooks'));
        });
    },

    populateMetrics() {
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'CEO' };
        // -- Companies --
        const compGrid = document.getElementById('metricsCompanies');
        if (compGrid) {
            let html = '<div class="metrics-company-grid">';
            BUILDINGS.forEach(b => {
                const npc = NPC_DATA.find(n => n.region.toUpperCase() === b.name.toUpperCase() || n.region.toUpperCase() === b.name);
                const isCompleted = State.completedRegions.some(r => r.toUpperCase() === b.name.toUpperCase());
                const isLocked = State.lockedRegion && State.lockedRegion.toUpperCase() === b.name.toUpperCase();
                const logo = COMPANY_LOGOS[b.name] || { icon: '?', font: 'bold 16px sans-serif' };
                const stage = npc ? (STAGE_PT[npc.stage] || npc.stage) : '';
                const statusIcon = isCompleted ? '<span style="color:#22c55e">&#10003;</span>' : (isLocked ? '<span style="color:#fbbf24">&#9679;</span>' : '<span style="color:#475569">&#9711;</span>');
                const cardClass = isCompleted ? 'completed' : (isLocked ? '' : 'locked');
                // Custom SVG for brands that need vector logos; text icon for others
                let logoContent = logo.icon;
                if (logo.noLogo) {
                    logoContent = '';
                } else if (logo.customDraw === 'apple') {
                    logoContent = '<svg viewBox="-16 -18 32 34" width="22" height="22"><path d="M0-10C3-12 8-12 10-8 12-4 12 2 10 6 8 10 5 14 0 14-5 14-8 10-10 6-12 2-12-4-10-8-8-12-3-12 0-10Z" fill="' + b.color + '"/><circle cx="12" cy="-4" r="5" fill="#0f172a"/><path d="M0-10Q1-15 2-16" stroke="' + b.color + '" stroke-width="1.4" fill="none" stroke-linecap="round"/><path d="M2-15Q6-17 8-14Q6-13 2-15Z" fill="' + b.color + '"/></svg>';
                } else if (logo.customDraw === 'microsoft') {
                    logoContent = '<svg viewBox="0 0 22 22" width="22" height="22"><rect x="1" y="1" width="9" height="9" fill="#f25022"/><rect x="12" y="1" width="9" height="9" fill="#7fba00"/><rect x="1" y="12" width="9" height="9" fill="#00a4ef"/><rect x="12" y="12" width="9" height="9" fill="#ffb900"/></svg>';
                } else if (logo.customDraw === 'disney') {
                    logoContent = '<svg viewBox="-16 -16 32 26" width="22" height="18"><rect x="-10" y="2" width="20" height="6" fill="' + b.color + '"/><rect x="-8" y="-1" width="16" height="4" fill="' + b.color + '"/><rect x="-9" y="-4" width="3" height="6" fill="' + b.color + '"/><rect x="-4" y="-6" width="3" height="8" fill="' + b.color + '"/><rect x="1" y="-6" width="3" height="8" fill="' + b.color + '"/><rect x="6" y="-4" width="3" height="6" fill="' + b.color + '"/><polygon points="-7.5,-8 -9.5,-4 -5.5,-4" fill="' + b.color + '"/><polygon points="-2.5,-11 -4.5,-6 -0.5,-6" fill="' + b.color + '"/><polygon points="2.5,-11 0.5,-6 4.5,-6" fill="' + b.color + '"/><polygon points="7.5,-8 5.5,-4 9.5,-4" fill="' + b.color + '"/><polygon points="0,-14 -2,-6 2,-6" fill="' + b.color + '"/><path d="M-13,2 A13,13 0 0,1 13,2" stroke="' + b.color + '" stroke-width="1.2" fill="none"/></svg>';
                } else if (logo.customDraw === 'google') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12,5 A7,7 0 1,0 19,12 L12,12" fill="none" stroke="#4285f4" stroke-width="3"/><path d="M12,5 A7,7 0 0,0 5.5,9" fill="none" stroke="#ea4335" stroke-width="3"/><path d="M5.5,9 A7,7 0 0,0 5.5,15" fill="none" stroke="#fbbc05" stroke-width="3"/><path d="M5.5,15 A7,7 0 0,0 12,19" fill="none" stroke="#34a853" stroke-width="3"/><rect x="11" y="10.5" width="8.5" height="3" fill="#4285f4"/></svg>';
                } else if (logo.customDraw === 'amazon') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><text x="8" y="13" font-size="14" font-weight="bold" fill="#111" font-family="sans-serif">a</text><path d="M4,18 Q12,23 20,16" stroke="#ff9900" stroke-width="2.2" fill="none" stroke-linecap="round"/><polygon points="20,16 17,18.5 19,19" fill="#ff9900"/></svg>';
                } else if (logo.customDraw === 'mercadolivre') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10" fill="#ffe600" stroke="#2d3277" stroke-width="1.8"/><path d="M6,13 Q9,8 12,11" stroke="#2d3277" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M18,13 Q15,8 12,11" stroke="#2d3277" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>';
                } else if (logo.customDraw === 'paypal') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><text x="13.5" y="15.5" font-size="17" font-weight="bold" fill="#003087" font-family="sans-serif">P</text><text x="10.5" y="13.5" font-size="17" font-weight="bold" fill="#009cde" font-family="sans-serif">P</text></svg>';
                } else if (logo.customDraw === 'spacex') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><text x="12" y="15" font-size="16" font-weight="bold" text-anchor="middle" fill="#111" font-family="sans-serif">X</text><path d="M3,13 Q12,6 21,9" stroke="#111" stroke-width="1.2" fill="none" stroke-linecap="round"/></svg>';
                } else if (logo.customDraw === 'itau') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><rect x="2" y="2" width="20" height="20" rx="5" fill="#ec7000"/><rect x="4.5" y="4.5" width="15" height="15" rx="4" fill="#fff"/><text x="12" y="15.5" font-size="9" font-weight="bold" text-anchor="middle" fill="#ec7000" font-family="sans-serif">ita\u00fa</text></svg>';
                } else if (logo.customDraw === 'aurora_labs') {
                    logoContent = '<svg viewBox="0 0 24 24" width="22" height="22"><g transform="translate(12,12)" stroke="#111" stroke-width="1.8" fill="none" stroke-linecap="round"><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(0)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(0)"/><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(60)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(60)"/><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(120)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(120)"/><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(180)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(180)"/><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(240)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(240)"/><line x1="0" y1="-8" x2="0" y2="-3" transform="rotate(300)"/><path d="M3.8,-1.7 A4.5,4.5 0 0,1 -1,5" transform="rotate(300)"/></g></svg>';
                }
                html += '<div class="metrics-company-card ' + cardClass + '">';
                html += '<div class="metrics-company-logo" style="background:' + b.color + '20;border-color:' + b.color + ';color:' + b.color + ';">' + logoContent + '</div>';
                html += '<div class="metrics-company-info"><div class="metrics-company-name">' + b.name + '</div><div class="metrics-company-stage">' + stage + (npc ? ' -- ' + npc.name : '') + '</div></div>';
                html += '<div class="metrics-company-status">' + statusIcon + '</div>';
                html += '</div>';
            });
            html += '</div>';
            compGrid.innerHTML = html;
        }
        // -- Books --
        const bookGrid = document.getElementById('metricsBooks');
        if (bookGrid) {
            let html = '<div class="metrics-book-grid">';
            BOOKS_DATA.forEach(book => {
                const isCollected = State.collectedBooks.includes(book.id);
                const cardClass = isCollected ? 'collected' : 'missing';
                const statusIcon = isCollected ? '<span style="color:#a78bfa">&#10003;</span>' : '<span style="color:#475569">&#9711;</span>';
                html += '<div class="metrics-book-card ' + cardClass + '">';
                html += '<div class="metrics-book-icon" style="background:' + book.color + '30;color:' + book.color + ';">&#128214;</div>';
                html += '<div class="metrics-book-info"><div class="metrics-book-title">' + book.title + '</div><div class="metrics-book-author">' + book.author + '</div></div>';
                html += '<div class="metrics-book-status">' + statusIcon + '</div>';
                html += '</div>';
            });
            html += '</div>';
            bookGrid.innerHTML = html;
        }
        // -- Footer counts --
        const cc = document.getElementById('metricsCompanyCount');
        if (cc) cc.textContent = State.completedRegions.length + ' / ' + BUILDINGS.length + ' empresas';
        const bc = document.getElementById('metricsBookCount');
        if (bc) bc.textContent = State.collectedBooks.length + ' / ' + BOOKS_DATA.length + ' livros';
    },

    showChallenge(challenge) {
        State.isInChallenge = true;
        State._actionCooldownUntil = performance.now() + 300;
        SFX.pauseMusic();
        SFX.challengeOpen();
        document.getElementById('challengeMentor').textContent = challenge.mentor || 'MENTOR';
        document.getElementById('challengeTitle').textContent = challenge.title || '---';
        document.getElementById('challengeRegion').textContent = challenge.region || '';
        document.getElementById('challengeDesc').textContent = challenge.description || '';

        const code = document.getElementById('challengeCode');
        if (challenge.context_code) { code.textContent = challenge.context_code; code.style.display = 'block'; }
        else { code.textContent = ''; code.style.display = 'none'; }

        const opts = document.getElementById('challengeOptions');
        opts.innerHTML = '';
        challenge.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'option-btn';
            btn.textContent = opt.text;
            btn.onclick = () => Game.submitAnswer(challenge.id, idx);
            opts.appendChild(btn);
        });

        document.getElementById('challengeFeedback').innerHTML = '';
        document.getElementById('challengeActions').style.display = 'none';
        document.getElementById('challengeOverlay').classList.add('visible');
    },

    hideChallenge(opts = {}) {
        State.isInChallenge = false;
        document.getElementById('challengeOverlay').classList.remove('visible');
        if (opts.resumeMusic !== false) SFX.resumeMusic();
    },

    showFeedback(result) {
        State._actionCooldownUntil = performance.now() + 300;
        const fb = document.getElementById('challengeFeedback');
        const ok = result.outcome === 'correct';
        fb.innerHTML = `<div class="feedback-box ${ok ? 'correct' : 'wrong'}">
            <strong>${ok ? 'CORRETO' : 'INCORRETO'}</strong><br><br>
            ${result.explanation}
            ${!ok && result.errors_remaining !== undefined ? '<br><br>Erros restantes: ' + result.errors_remaining + ' / 2' : ''}
        </div>`;
        document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
        document.getElementById('challengeActions').style.display = 'flex';
    },

    _promotionCallback: null,

    showPromotion(stage, msg, onDismiss) {
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'CEO' };
        document.getElementById('promotionMessage').textContent = msg;
        document.getElementById('promotionStage').textContent = STAGE_PT[stage] || stage;
        document.getElementById('promotionOverlay').style.display = 'flex';
        State._actionCooldownUntil = performance.now() + 400;
        this._promotionCallback = onDismiss || null;
        SFX.promote();
    },

    hidePromotion() {
        document.getElementById('promotionOverlay').style.display = 'none';
        const cb = this._promotionCallback;
        this._promotionCallback = null;
        if (cb) cb();
    },

    showGameOver(stats) {
        SFX.stopMusic();
        SFX.gameOver();
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'CEO' };
        document.getElementById('gameoverStats').innerHTML =
            `Cargo: ${STAGE_PT[stats.stage] || stats.stage}<br>Pontuacao: ${stats.total_score || stats.score || 0}<br>Tentativas: ${stats.total_attempts || '---'}<br>Fim de Jogo: ${stats.game_over_count || 1}`;
        UI.showScreen('screen-gameover');
    },

    showVictory(player) {
        SFX.stopMusic();
        SFX.victory();
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'CEO' };
        document.getElementById('victoryStats').innerHTML =
            `Engenheiro: ${player.name}<br>Cargo: ${STAGE_PT[player.stage] || player.stage}<br>Pontuacao: ${player.score}<br>Desafios: ${player.completed_challenges.length}<br>Tentativas: ${player.total_attempts}`;
        UI.showScreen('screen-victory');
        this._startVictoryCelebration(player);
    },

    _startVictoryCelebration(player) {
        const canvas = document.getElementById('victoryCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        // Responsive canvas
        const resize = () => { canvas.width = canvas.clientWidth; canvas.height = canvas.clientHeight; };
        resize();
        window.addEventListener('resize', resize);

        const startTime = performance.now();
        let animId = null;
        const COLORS7 = ['#fbbf24', '#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#ec4899', '#f97316'];

        // -- Character positions in VIRTUAL world (wide, we pan across it) --
        const CHAR_SPACING = 72;
        const totalNpcs = NPC_DATA.length;
        const VIRTUAL_W = (totalNpcs + 6) * CHAR_SPACING;
        const CENTER_X = VIRTUAL_W / 2;

        // Front row: Player center + NPCs arranged left/right of player
        const frontRow = [];
        frontRow.push({
            name: player.name || 'PLAYER', targetX: CENTER_X, x: CENTER_X, arrived: true,
            isPlayer: true, look: { skinTone: World.getSkinColor(State.avatarIndex || 0), shirt: '#fbbf24', pants: '#1e293b' },
            delay: 0, scale: 1.35
        });
        // Sort NPCs: distribute evenly left and right of center
        NPC_DATA.forEach((npc, i) => {
            const side = i % 2 === 0 ? 1 : -1;
            const slot = Math.floor(i / 2) + 1;
            const tgtX = CENTER_X + side * slot * CHAR_SPACING;
            const fromLeft = tgtX < CENTER_X;
            frontRow.push({
                name: npc.name.split(' ').slice(-1)[0], fullName: npc.name,
                targetX: tgtX,
                x: fromLeft ? -100 - Math.random() * 300 : VIRTUAL_W + 100 + Math.random() * 300,
                arrived: false, isPlayer: false, look: npc.look || {},
                delay: 600 + i * 150 + Math.random() * 100, fromLeft, scale: 1.0
            });
        });

        // Back row: Book authors (smaller, behind)
        const backRow = [];
        const seenAuthors = new Set();
        BOOKS_DATA.forEach(bk => {
            if (!seenAuthors.has(bk.author)) {
                seenAuthors.add(bk.author);
                const i = backRow.length;
                const side = i % 2 === 0 ? -1 : 1;
                const slot = Math.floor(i / 2) + 1;
                const tgtX = CENTER_X + side * slot * 56;
                const fromLeft = tgtX < CENTER_X;
                backRow.push({
                    name: bk.author.split(' ').slice(-1)[0],
                    targetX: tgtX,
                    x: fromLeft ? -80 - Math.random() * 200 : VIRTUAL_W + 80 + Math.random() * 200,
                    arrived: false, delay: 2500 + i * 200, fromLeft, scale: 0.65
                });
            }
        });

        // Camera panning: starts centered on player, slowly pans left then right to reveal all
        let camX = CENTER_X;
        const PAN_SPEED = 0.35;
        let panPhase = 0; // 0=center, 1=pan-left, 2=pan-right, 3=return-center, 4=done
        let panTimer = 0;

        // Confetti (abundant)
        const confetti = [];
        for (let i = 0; i < 250; i++) {
            confetti.push({
                x: Math.random() * 2000 - 400,
                y: -20 - Math.random() * 1200,
                vx: (Math.random() - 0.5) * 1.8,
                vy: 0.8 + Math.random() * 2.2,
                size: 3 + Math.random() * 6,
                color: COLORS7[Math.floor(Math.random() * 7)],
                rot: Math.random() * 360, rotV: (Math.random() - 0.5) * 10,
                type: Math.random() > 0.5 ? 'rect' : 'circle'
            });
        }

        // Firework bursts
        const fireworks = [];
        const spawnFirework = () => {
            const fx = Math.random() * 1200 - 100;
            const fy = 30 + Math.random() * 150;
            const count = 20 + Math.floor(Math.random() * 20);
            const color = COLORS7[Math.floor(Math.random() * 7)];
            for (let i = 0; i < count; i++) {
                const angle = (i / count) * Math.PI * 2;
                const speed = 1.5 + Math.random() * 3;
                fireworks.push({
                    x: fx, y: fy, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 0.5,
                    life: 60 + Math.random() * 40, maxLife: 100, color, size: 2 + Math.random() * 2
                });
            }
        };
        let lastFirework = 0;

        // -- Drawing helpers --
        const drawChar = (c, t, drawX, groundY, sz) => {
            const s = sz || c.scale || 1.0;
            const L = c.look || {};
            const skin = L.skinTone || '#F5D0A9';
            const charH = 68 * s;
            const topY = groundY - charH;

            // Shadow
            ctx.fillStyle = 'rgba(0,0,0,0.18)';
            ctx.beginPath();
            ctx.ellipse(drawX, groundY + 2, 14 * s, 4 * s, 0, 0, Math.PI * 2);
            ctx.fill();

            // Legs
            ctx.fillStyle = L.pants || '#333';
            const legAnim = c.arrived ? Math.sin(t * 0.004 + c.targetX * 0.01) * 2 : Math.sin(t * 0.012) * 5;
            ctx.fillRect(drawX - 5 * s, topY + 48 * s + legAnim, 4 * s, 18 * s);
            ctx.fillRect(drawX + 1 * s, topY + 48 * s - legAnim, 4 * s, 18 * s);

            // Shoes
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(drawX - 6 * s, groundY - 3, 6 * s, 3);
            ctx.fillRect(drawX + 0, groundY - 3, 6 * s, 3);

            // Body
            const bodyC = L.suit || L.hoodie || L.turtleneck ? (L.suit || L.hoodie || '#111') : (L.shirt || '#555');
            ctx.fillStyle = bodyC;
            const bw = 24 * s, bh = 34 * s;
            ctx.fillRect(drawX - bw / 2, topY + 14 * s, bw, bh);

            // Arms -- celebratory wave
            const armAng = c.arrived ? Math.sin(t * 0.005 + c.targetX * 0.08) * 30 - 20 : Math.sin(t * 0.01) * 15;
            ctx.save();
            ctx.translate(drawX - bw / 2, topY + 18 * s);
            ctx.rotate(armAng * Math.PI / 180);
            ctx.fillStyle = bodyC;
            ctx.fillRect(-2 * s, 0, 5 * s, 18 * s);
            ctx.fillStyle = skin;
            ctx.fillRect(-1.5 * s, 16 * s, 4 * s, 7 * s);
            ctx.restore();
            ctx.save();
            ctx.translate(drawX + bw / 2, topY + 18 * s);
            ctx.rotate(-armAng * Math.PI / 180);
            ctx.fillStyle = bodyC;
            ctx.fillRect(-3 * s, 0, 5 * s, 18 * s);
            ctx.fillStyle = skin;
            ctx.fillRect(-2.5 * s, 16 * s, 4 * s, 7 * s);
            ctx.restore();

            // CEO label on player
            if (c.isPlayer) {
                ctx.fillStyle = '#0a0e1a';
                ctx.font = 'bold ' + Math.round(6 * s) + 'px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('CEO', drawX, topY + 34 * s);
            }

            // Tie
            if (L.tie) { ctx.fillStyle = L.tie; ctx.fillRect(drawX - 1.5, topY + 18 * s, 3, 16 * s); }

            // Head
            const headR = 11 * s;
            const headY = topY + 5 * s;
            ctx.fillStyle = skin;
            ctx.beginPath(); ctx.arc(drawX, headY, headR, 0, Math.PI * 2); ctx.fill();

            // Hair
            if (!L.bald && L.hairStyle !== 'bald') {
                ctx.fillStyle = L.hair || '#222';
                ctx.beginPath(); ctx.arc(drawX, headY - 3, headR + 1, Math.PI, Math.PI * 2); ctx.fill();
            }

            // Eyes
            const eyeY = headY + 2;
            const blink = Math.sin(t * 0.003 + c.targetX) > -0.92;
            ctx.fillStyle = '#fff';
            ctx.beginPath(); ctx.ellipse(drawX - 4 * s, eyeY, 2.5 * s, blink ? 2.5 * s : 0.6 * s, 0, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.ellipse(drawX + 4 * s, eyeY, 2.5 * s, blink ? 2.5 * s : 0.6 * s, 0, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#111';
            ctx.beginPath(); ctx.arc(drawX - 3 * s, eyeY + 0.5, 1.3 * s, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(drawX + 5 * s, eyeY + 0.5, 1.3 * s, 0, Math.PI * 2); ctx.fill();

            // Glasses
            if (L.glasses) {
                ctx.strokeStyle = '#444'; ctx.lineWidth = 1;
                ctx.beginPath(); ctx.arc(drawX - 4 * s, eyeY, 3.5 * s, 0, Math.PI * 2); ctx.stroke();
                ctx.beginPath(); ctx.arc(drawX + 4 * s, eyeY, 3.5 * s, 0, Math.PI * 2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(drawX - 0.5 * s, eyeY); ctx.lineTo(drawX + 0.5 * s, eyeY); ctx.stroke();
            }

            // Mouth
            ctx.strokeStyle = '#333'; ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(drawX, headY + 6 * s, c.arrived ? 3.5 * s : 2.5 * s, 0.15 * Math.PI, 0.85 * Math.PI);
            ctx.stroke();

            // Gold glow halo around player
            if (c.isPlayer) {
                const glowAlpha = 0.12 + Math.sin(t * 0.003) * 0.08;
                ctx.save();
                ctx.globalAlpha = glowAlpha;
                ctx.shadowColor = '#fbbf24';
                ctx.shadowBlur = 30;
                ctx.fillStyle = '#fbbf24';
                ctx.beginPath(); ctx.arc(drawX, topY + charH * 0.4, charH * 0.45, 0, Math.PI * 2); ctx.fill();
                ctx.restore();
            }

            // Name tag -- above head with readable background
            if (c.arrived) {
                const label = c.isPlayer ? (c.name || '') : (c.fullName || c.name || '');
                const fSize = Math.round((c.isPlayer ? 9 : 7) * s);
                ctx.font = (c.isPlayer ? 'bold ' : '') + fSize + 'px sans-serif';
                ctx.textAlign = 'center';
                const tw = ctx.measureText(label).width;
                const tagY = topY - 8 * s;
                const padX = 3, padY = 2;
                ctx.fillStyle = c.isPlayer ? 'rgba(251,191,36,0.93)' : 'rgba(10,14,26,0.80)';
                ctx.fillRect(drawX - tw / 2 - padX, tagY - fSize - padY, tw + padX * 2, fSize + padY * 2 + 1);
                ctx.fillStyle = c.isPlayer ? '#000' : '#e5e7eb';
                ctx.fillText(label, drawX, tagY);
            }
        };

        const animate = (now) => {
            const W = canvas.width;
            const H = canvas.height;
            const elapsed = now - startTime;
            const FRONT_GROUND = H * 0.38;
            const BACK_GROUND = H * 0.24;

            // Camera panning logic
            if (panPhase === 0 && elapsed > 4000) { panPhase = 1; panTimer = now; }
            if (panPhase === 1) {
                camX -= PAN_SPEED * 1.5;
                const leftEdge = CENTER_X - (totalNpcs / 2 + 1) * CHAR_SPACING;
                if (camX < leftEdge + 200 || now - panTimer > 5000) { panPhase = 2; panTimer = now; }
            }
            if (panPhase === 2) {
                camX += PAN_SPEED * 1.5;
                const rightEdge = CENTER_X + (totalNpcs / 2 + 1) * CHAR_SPACING;
                if (camX > rightEdge - 200 || now - panTimer > 10000) { panPhase = 3; panTimer = now; }
            }
            if (panPhase === 3) {
                const diff = CENTER_X - camX;
                camX += diff * 0.02;
                if (Math.abs(diff) < 2) { camX = CENTER_X; panPhase = 4; }
            }

            // Virtual-to-screen transform
            const toScreen = (vx) => (vx - camX) + W / 2;

            ctx.clearRect(0, 0, W, H);

            // Sky gradient
            const skyGrad = ctx.createLinearGradient(0, 0, 0, H);
            skyGrad.addColorStop(0, '#050a1e');
            skyGrad.addColorStop(0.4, '#0f1533');
            skyGrad.addColorStop(0.7, '#1a2040');
            skyGrad.addColorStop(1, '#0d1225');
            ctx.fillStyle = skyGrad;
            ctx.fillRect(0, 0, W, H);

            // Stars (parallax)
            for (let i = 0; i < 100; i++) {
                const sx = ((i * 137.508 + Math.sin(now * 0.0005 + i) * 1.5) % (W + 200)) - 100;
                const sy = ((i * 67.3 + Math.cos(now * 0.0004 + i) * 1) % (H * 0.45));
                const sz = 0.4 + (i % 4) * 0.4;
                ctx.globalAlpha = 0.2 + Math.sin(now * 0.0015 + i * 0.7) * 0.25;
                ctx.fillStyle = i % 5 === 0 ? '#fbbf24' : '#fff';
                ctx.beginPath(); ctx.arc(sx, sy, sz, 0, Math.PI * 2); ctx.fill();
            }
            ctx.globalAlpha = 1.0;

            // Distant city silhouette
            ctx.fillStyle = '#0c1020';
            for (let i = 0; i < 30; i++) {
                const bx = toScreen(i * 110 - 200) * 0.3 + i * 40;
                const bw = 25 + (i * 7) % 35;
                const bh = 30 + (i * 13) % 60;
                ctx.fillRect(bx, BACK_GROUND - 40 - bh, bw, bh + 40);
            }

            // Ground layers
            const groundGrad = ctx.createLinearGradient(0, BACK_GROUND - 10, 0, H);
            groundGrad.addColorStop(0, '#1a2744');
            groundGrad.addColorStop(0.3, '#162038');
            groundGrad.addColorStop(1, '#0d1225');
            ctx.fillStyle = groundGrad;
            ctx.fillRect(0, BACK_GROUND - 10, W, H - BACK_GROUND + 10);

            // Ground line highlights
            ctx.fillStyle = '#243352';
            ctx.fillRect(0, BACK_GROUND - 10, W, 2);
            ctx.fillStyle = '#1e2d48';
            ctx.fillRect(0, FRONT_GROUND, W, 2);

            // "VALE DO SILICIO" sign -- centered, behind back row
            const signScreenX = toScreen(CENTER_X);
            const signW = 280;
            const signH = 55;
            const signDrawX = signScreenX - signW / 2;
            const signDrawY = BACK_GROUND - 130;

            ctx.fillStyle = '#3d2a10';
            ctx.fillRect(signScreenX - 5, signDrawY + signH, 10, 80);
            ctx.fillStyle = '#2d1f0e';
            ctx.fillRect(signDrawX, signDrawY, signW, signH);
            ctx.strokeStyle = '#c9a34e'; ctx.lineWidth = 2;
            ctx.strokeRect(signDrawX + 1, signDrawY + 1, signW - 2, signH - 2);
            ctx.fillStyle = '#fbbf24';
            ctx.font = 'bold 22px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText('VALE DO SILICIO', signScreenX, signDrawY + signH / 2 - 7);
            ctx.fillStyle = '#8899aa'; ctx.font = '11px sans-serif';
            ctx.fillText('Silicon Valley', signScreenX, signDrawY + signH / 2 + 12);

            // Draw back row (authors)
            backRow.forEach(a => {
                if (elapsed < a.delay) return;
                if (!a.arrived) {
                    const spd = 2.5;
                    if (a.fromLeft) { a.x += spd; if (a.x >= a.targetX) { a.x = a.targetX; a.arrived = true; } }
                    else { a.x -= spd; if (a.x <= a.targetX) { a.x = a.targetX; a.arrived = true; } }
                }
                const sx = toScreen(a.x);
                if (sx > -60 && sx < W + 60) {
                    ctx.globalAlpha = 0.6;
                    const bounce = a.arrived ? Math.abs(Math.sin(now * 0.002 + a.targetX * 0.04)) * 3 : 0;
                    drawChar(a, now, sx, BACK_GROUND - bounce, a.scale);
                    ctx.globalAlpha = 1.0;
                }
            });

            // Draw front row (player + NPCs)
            // Sort by targetX for proper Z-order (further from center = drawn first)
            const sorted = [...frontRow].sort((a, b) => {
                if (a.isPlayer) return 1; // player drawn last (on top)
                if (b.isPlayer) return -1;
                return Math.abs(a.targetX - CENTER_X) - Math.abs(b.targetX - CENTER_X);
            });
            sorted.forEach(c => {
                if (elapsed < c.delay) return;
                if (!c.arrived) {
                    const spd = 3.0;
                    if (c.fromLeft) { c.x += spd; if (c.x >= c.targetX) { c.x = c.targetX; c.arrived = true; } }
                    else { c.x -= spd; if (c.x <= c.targetX) { c.x = c.targetX; c.arrived = true; } }
                }
                const sx = toScreen(c.x);
                if (sx > -80 && sx < W + 80) {
                    const bounce = c.arrived ? Math.abs(Math.sin(now * 0.003 + c.targetX * 0.05)) * 5 : 0;
                    drawChar(c, now, sx, FRONT_GROUND - bounce, c.scale);
                }
            });

            // Confetti (screen-space)
            confetti.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                p.rot += p.rotV;
                if (p.y > H + 20) { p.y = -15; p.x = Math.random() * (W + 200) - 100; }
                if (p.x < -50) p.x = W + 30;
                if (p.x > W + 50) p.x = -30;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot * Math.PI / 180);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = 0.75;
                if (p.type === 'circle') {
                    ctx.beginPath(); ctx.arc(0, 0, p.size * 0.4, 0, Math.PI * 2); ctx.fill();
                } else {
                    ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
                }
                ctx.globalAlpha = 1.0;
                ctx.restore();
            });

            // Firework bursts
            if (elapsed > 2000 && now - lastFirework > 800 + Math.random() * 600) {
                spawnFirework();
                lastFirework = now;
            }
            for (let i = fireworks.length - 1; i >= 0; i--) {
                const f = fireworks[i];
                f.x += f.vx; f.y += f.vy; f.vy += 0.03; f.life--;
                if (f.life <= 0) { fireworks.splice(i, 1); continue; }
                const alpha = f.life / f.maxLife;
                ctx.globalAlpha = alpha * 0.9;
                ctx.fillStyle = f.color;
                ctx.beginPath(); ctx.arc(f.x, f.y, f.size * alpha, 0, Math.PI * 2); ctx.fill();
                // Trail
                ctx.globalAlpha = alpha * 0.3;
                ctx.beginPath(); ctx.arc(f.x - f.vx, f.y - f.vy, f.size * alpha * 0.6, 0, Math.PI * 2); ctx.fill();
            }
            ctx.globalAlpha = 1.0;

            // Spotlight glow on player
            const playerScreenX = toScreen(CENTER_X);
            const spotGrad = ctx.createRadialGradient(playerScreenX, FRONT_GROUND - 40, 10, playerScreenX, FRONT_GROUND - 40, 120);
            spotGrad.addColorStop(0, 'rgba(251, 191, 36, 0.06)');
            spotGrad.addColorStop(1, 'rgba(251, 191, 36, 0)');
            ctx.fillStyle = spotGrad;
            ctx.fillRect(playerScreenX - 150, FRONT_GROUND - 160, 300, 200);

            // Vignette edges
            const vigL = ctx.createLinearGradient(0, 0, W * 0.15, 0);
            vigL.addColorStop(0, 'rgba(5, 10, 30, 0.7)'); vigL.addColorStop(1, 'rgba(5, 10, 30, 0)');
            ctx.fillStyle = vigL; ctx.fillRect(0, 0, W * 0.15, H);
            const vigR = ctx.createLinearGradient(W, 0, W * 0.85, 0);
            vigR.addColorStop(0, 'rgba(5, 10, 30, 0.7)'); vigR.addColorStop(1, 'rgba(5, 10, 30, 0)');
            ctx.fillStyle = vigR; ctx.fillRect(W * 0.85, 0, W * 0.15, H);

            animId = requestAnimationFrame(animate);
        };

        if (this._victoryAnimId) cancelAnimationFrame(this._victoryAnimId);
        this._victoryAnimId = null;
        animId = requestAnimationFrame(animate);
        this._victoryAnimId = animId;
    },
};

const Learning = {
    _pendingContinue: null,

    _storageKey() {
        if (!State.sessionId) return null;
        return 'garage_learning_' + State.sessionId;
    },

    _safeArray(v) {
        return Array.isArray(v) ? v.filter(Boolean) : [];
    },

    _sanitizeState(raw) {
        const data = raw || {};
        return {
            stageBriefingsSeen: this._safeArray(data.stageBriefingsSeen),
            companyPrepSeen: this._safeArray(data.companyPrepSeen),
            livePrepSeen: this._safeArray(data.livePrepSeen),
        };
    },

    _normalizeRegion(region) {
        return (region || '').toString().trim().toUpperCase();
    },

    _pushUnique(list, value) {
        if (!value) return;
        if (!list.includes(value)) list.push(value);
    },

    _setFlags(open) {
        State.isInPrep = open;
        if (open && World.keys) {
            World.keys['ArrowLeft'] = false;
            World.keys['ArrowRight'] = false;
            World.keys['ArrowUp'] = false;
        }
    },

    _save() {
        const key = this._storageKey();
        if (!key) return;
        try {
            localStorage.setItem(key, JSON.stringify(State.learning));
        } catch (_e) {
            // best effort
        }
    },

    _read() {
        const key = this._storageKey();
        if (!key) return null;
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return null;
            return this._sanitizeState(JSON.parse(raw));
        } catch (_e) {
            return null;
        }
    },

    _buildBootstrap(player, challenges) {
        const base = this._sanitizeState({});
        if (!player || !Array.isArray(challenges)) return base;

        const completed = Array.isArray(player.completed_challenges) ? player.completed_challenges : [];
        const totalAttempts = Number(player.total_attempts || 0);

        if (completed.length > 0) {
            const regionMap = {};
            for (const c of challenges) {
                if (!c.region || !c.id) continue;
                if (!regionMap[c.region]) regionMap[c.region] = [];
                regionMap[c.region].push(c.id);
            }

            const engagedRegions = new Set();
            for (const c of challenges) {
                if (c && c.region && completed.includes(c.id)) engagedRegions.add(c.region);
            }
            for (const region of engagedRegions) {
                this._pushUnique(base.companyPrepSeen, region);
            }

            for (const [region, ids] of Object.entries(regionMap)) {
                if (ids.length > 0 && ids.every(id => completed.includes(id))) {
                    this._pushUnique(base.livePrepSeen, region);
                }
            }
        }

        if (totalAttempts > 0) {
            const idx = LEARNING_STAGE_ORDER.indexOf(player.stage);
            if (idx >= 0) {
                for (let i = 0; i <= idx; i++) {
                    this._pushUnique(base.stageBriefingsSeen, LEARNING_STAGE_ORDER[i]);
                }
            }
        }
        return base;
    },

    syncSessionState(player, challenges) {
        const stored = this._read();
        if (stored) {
            State.learning = stored;
            return;
        }
        State.learning = this._buildBootstrap(player, challenges);
        this._save();
    },

    _escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    _setList(id, items) {
        const el = document.getElementById(id);
        if (!el) return;
        const safe = (Array.isArray(items) ? items : []).filter(Boolean);
        el.innerHTML = safe.map(item => '<li>' + this._escapeHtml(item) + '</li>').join('');
    },

    isOpen() {
        const overlay = document.getElementById('learningOverlay');
        return !!(overlay && overlay.style.display === 'flex');
    },

    cancel() {
        const overlay = document.getElementById('learningOverlay');
        if (overlay) overlay.style.display = 'none';
        this._pendingContinue = null;
        this._setFlags(false);
    },

    continue() {
        if (!this.isOpen()) return;
        const cb = this._pendingContinue;
        this.cancel();
        if (cb) cb();
    },

    _showPanel(config, onContinue) {
        const overlay = document.getElementById('learningOverlay');
        if (!overlay) {
            if (onContinue) onContinue();
            return;
        }

        document.getElementById('learningChip').textContent = config.chip || 'PREPARACAO';
        document.getElementById('learningStageLabel').textContent = config.stageLabel || '';
        document.getElementById('learningTitle').textContent = config.title || '';
        document.getElementById('learningSubtitle').textContent = config.subtitle || '';
        document.getElementById('learningSecAHead').textContent = config.secAHead || '';
        document.getElementById('learningSecBHead').textContent = config.secBHead || '';
        document.getElementById('learningSecCHead').textContent = config.secCHead || '';
        document.getElementById('learningWarmupText').textContent = config.warmup || '';

        this._setList('learningSecAList', config.secAItems || []);
        this._setList('learningSecBList', config.secBItems || []);
        this._setList('learningSecCList', config.secCItems || []);

        const btn = document.getElementById('learningContinueBtn');
        if (btn) btn.onclick = () => this.continue();

        this._pendingContinue = onContinue || null;
        overlay.style.display = 'flex';
        this._setFlags(true);
        State._actionCooldownUntil = performance.now() + 400;
    },

    _normalizeText(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    },

    _regionTopics(region) {
        const regionChallenges = (State.challenges || []).filter(c => c.region === region);
        if (regionChallenges.length === 0) return ['Foco: leitura do problema e construcao de solucao incremental.'];
        const categories = [...new Set(regionChallenges.map(c => c.category))];
        return categories
            .map(cat => LEARNING_CATEGORY_GUIDE[cat])
            .filter(Boolean)
            .slice(0, 3);
    },

    _buildLiveCodingPlan(challenge) {
        const concept = this._normalizeText(challenge && challenge.concept);
        if (concept.includes('hash')) {
            return [
                'Escolha Map/Set e defina a chave certa antes de codar.',
                'Faca uma passada principal e use lookup O(1).',
                'Valide duplicata, colisao logica e caso nao encontrado.',
            ];
        }
        if (concept.includes('stack') || concept.includes('lifo') || concept.includes('bracket')) {
            return [
                'Defina claramente push/pop e o estado inicial da pilha.',
                'Para cada entrada, atualize estado e valide imediatamente.',
                'No final, confirme se a pilha ficou no estado esperado.',
            ];
        }
        if (concept.includes('queue') || concept.includes('fifo')) {
            return [
                'Defina ordem de entrada e ordem de consumo.',
                'Use while com condicao de parada explicita.',
                'Garanta que a fila termina vazia no cenario final.',
            ];
        }
        if (concept.includes('binary') || concept.includes('log n')) {
            return [
                'Confirme pre-condicao: estrutura ordenada.',
                'Atualize low/high sem perder o caso de igualdade.',
                'Pare quando low > high e retorne fallback correto.',
            ];
        }
        if (concept.includes('sort') || concept.includes('merge')) {
            return [
                'Separe fase de dividir e fase de combinar.',
                'Mantenha indices consistentes em toda iteracao.',
                'Teste com entrada pequena e elementos repetidos.',
            ];
        }
        if (concept.includes('grafo') || concept.includes('graph') || concept.includes('bfs')) {
            return [
                'Declare estrutura de vizinhos e set de visitados.',
                'Inicialize fila com no inicial antes do loop.',
                'Marque visitado no momento certo para evitar repeticao.',
            ];
        }
        if (concept.includes('dinamica') || concept.includes('kadane') || concept.includes('subproblemas')) {
            return [
                'Defina o estado minimo que precisa ser carregado.',
                'Escreva a recorrencia em frase antes do codigo.',
                'Itere com base cases claros e atualizacao deterministica.',
            ];
        }
        if (concept.includes('arvore') || concept.includes('tree') || concept.includes('ponteiro') || concept.includes('pointer')) {
            return [
                'Desenhe mentalmente um exemplo pequeno de nos.',
                'Defina caso base para null/folha primeiro.',
                'Aplique transformacao e avance ponteiros sem perder referencia.',
            ];
        }
        return [
            'Traduzir enunciado para entrada, processamento e saida.',
            'Implementar versao simples primeiro e validar.',
            'Refinar para legibilidade e complexidade esperada.',
        ];
    },

    showStageBriefingIfNeeded(stage, onContinue) {
        const normalizedStage = stage || 'Intern';
        if (State.learning.stageBriefingsSeen.includes(normalizedStage)) {
            if (onContinue) onContinue();
            return false;
        }

        const profile = LEARNING_STAGE_PROFILE[normalizedStage] || LEARNING_STAGE_PROFILE.Intern;
        this._showPanel({
            chip: 'MENTALIDADE DE CARREIRA',
            stageLabel: LEARNING_STAGE_PT[normalizedStage] || normalizedStage,
            title: 'Como pensa um engenheiro ' + (LEARNING_STAGE_PT[normalizedStage] || normalizedStage),
            subtitle: 'Antes de codar, alinhe o modo de raciocinio esperado neste nivel.',
            secAHead: 'Forma de pensar',
            secAItems: profile.thinking || [],
            secBHead: 'Principais preocupacoes',
            secBItems: profile.concerns || [],
            secCHead: 'Base Java deste nivel',
            secCItems: profile.javaFocus || [],
            warmup: 'Warm-up: explique em voz alta o plano antes de tocar no teclado. Engenheiro forte pensa primeiro, digita depois.',
        }, () => {
            this._pushUnique(State.learning.stageBriefingsSeen, normalizedStage);
            this._save();
            if (onContinue) onContinue();
        });
        return true;
    },

    showCompanyPrepIfNeeded(region, npc, onContinue) {
        if (!region) {
            if (onContinue) onContinue();
            return false;
        }

        const regionKey = this._normalizeRegion(region);
        const alreadySeen = State.learning.companyPrepSeen.some(r => this._normalizeRegion(r) === regionKey);
        if (alreadySeen) {
            if (onContinue) onContinue();
            return false;
        }

        const stage = (State.player && State.player.stage) || (npc && npc.stage) || 'Intern';
        const profile = LEARNING_STAGE_PROFILE[stage] || LEARNING_STAGE_PROFILE.Intern;
        const topics = this._regionTopics(region);

        this._showPanel({
            chip: 'PREPARACAO DE EMPRESA',
            stageLabel: (npc && npc.name) ? npc.name : (LEARNING_STAGE_PT[stage] || stage),
            title: 'Briefing tecnico: ' + region,
            subtitle: 'Voce vai resolver teoria + codigo. Prepare a mente antes de entrar na execucao.',
            secAHead: 'Mapa mental para esta fase',
            secAItems: profile.thinking || [],
            secBHead: 'Sintaxe Java para revisar antes',
            secBItems: profile.javaFocus || [],
            secCHead: 'Topicos desta empresa',
            secCItems: topics,
            warmup: 'Warm-up: defina em uma frase qual estrutura de dados voce pretende usar e por que ela reduz custo.',
        }, () => {
            this._pushUnique(State.learning.companyPrepSeen, region);
            this._save();
            if (onContinue) onContinue();
        });
        return true;
    },

    showLiveCodingPrepIfNeeded(region, challenge, onContinue) {
        if (!region || !challenge) {
            if (onContinue) onContinue();
            return false;
        }

        const regionKey = this._normalizeRegion(region);
        const alreadySeen = State.learning.livePrepSeen.some(r => this._normalizeRegion(r) === regionKey);
        if (alreadySeen) {
            if (onContinue) onContinue();
            return false;
        }

        const stage = (State.player && State.player.stage) || challenge.stage || 'Intern';
        const profile = LEARNING_STAGE_PROFILE[stage] || LEARNING_STAGE_PROFILE.Intern;
        const expectedClass = (challenge.fileName || 'Main.java').replace('.java', '');
        const plan = this._buildLiveCodingPlan(challenge);

        this._showPanel({
            chip: 'PRE-LIVE CODING',
            stageLabel: challenge.title || 'Desafio de codigo',
            title: 'Roteiro de execucao antes da IDE',
            subtitle: 'Meta: entrar no live coding com estrategia, nao no improviso.',
            secAHead: 'Checklist de sintaxe Java',
            secAItems: [
                'Classe publica com nome exato: ' + expectedClass + '.',
                'main/metodo com assinatura valida e chaves balanceadas.',
                '; no fim de declaracoes e uso coerente de tipos.',
            ],
            secBHead: 'Plano de algoritmo',
            secBItems: plan,
            secCHead: 'Visao de engenharia do nivel',
            secCItems: profile.concerns || [],
            warmup: 'Warm-up: faca um dry-run manual com um exemplo e escreva a saida esperada antes de clicar EXECUTAR.',
        }, () => {
            this._pushUnique(State.learning.livePrepSeen, region);
            this._save();
            if (onContinue) onContinue();
        });
        return true;
    },
};

/**
 * Reconstruct State.completedRegions from server data.
 * A region is considered complete when all its theory challenges are in completed_challenges.
 * (IDE completion is implied: player cannot leave a building without solving the IDE challenge.)
 */
function _reconstructCompletedRegions() {
    if (!State.player || !State.challenges) return;
    State.completedRegions = [];
    const regionMap = {};
    for (const c of State.challenges) {
        if (!c.region) continue;
        if (!regionMap[c.region]) regionMap[c.region] = [];
        regionMap[c.region].push(c.id);
    }
    for (const [region, ids] of Object.entries(regionMap)) {
        if (ids.length > 0 && ids.every(id => State.player.completed_challenges.includes(id))) {
            State.completedRegions.push(region);
        }
    }
}

function _allCompaniesComplete() {
    return BUILDINGS.length > 0 && State.completedRegions.length >= BUILDINGS.length;
}

// ---- game controller ----
const Game = {
    async start() {
        const name = document.getElementById('playerName').value.trim();
        if (!name) { alert('Digite seu nome.'); return; }
        const av = UI.getSelectedAvatar();
        SFX.menuConfirm();

        try {
            // Reset any previous world state tracking
            WorldStatePersistence.reset();

            const data = await API.post('/api/start', {
                player_name: name,
                gender: av.gender,
                ethnicity: av.ethnicity,
                avatar_index: av.index,
                language: document.getElementById('playerLang').value,
            });
            State.sessionId = data.session_id;
            State.player = data.player;
            State.avatarIndex = av.index;
            localStorage.setItem('garage_session_id', data.session_id);

            // Reset world state for new game
            State.collectedBooks = [];
            State.completedRegions = [];
            State.lockedRegion = null;
            State.lockedNpc = null;
            State.doorAnimBuilding = null;

            State.challenges = await API.get('/api/challenges');
            Learning.syncSessionState(State.player, State.challenges);

            World.init(av.index, 100);
            UI.updateHUD(State.player);
            UI.showScreen('screen-world');

            // Start periodic save for position persistence
            WorldStatePersistence.startPeriodicSave(30000);

            // Start heartbeat for online tracking
            Heartbeat.start();

            Learning.showStageBriefingIfNeeded(State.player.stage);
        } catch (e) { alert('Erro: ' + e.message); }
    },

    async loadSession(silent = false) {
        const id = localStorage.getItem('garage_session_id');
        if (!id) { if (!silent) alert('Nenhuma sessao salva.'); return false; }
        try {
            State.player = await API.get('/api/session/' + id);
            State.sessionId = id;
            State.challenges = await API.get('/api/challenges');
            Learning.syncSessionState(State.player, State.challenges);

            // Restore world state from server (books, regions, position)
            WorldStatePersistence.restore(State.player);

            // Initialize world with saved position
            const savedX = State.player.player_world_x || 100;
            World.init(State.player.character ? State.player.character.avatar_index : 0, savedX);
            State.avatarIndex = State.player.character ? State.player.character.avatar_index : 0;

            // _reconstructCompletedRegions is no longer needed as we restore from server
            // but keep it as fallback for backward compatibility
            if (!State.completedRegions || State.completedRegions.length === 0) {
                _reconstructCompletedRegions();
            }

            UI.updateHUD(State.player);
            UI.showScreen('screen-world');

            // Start periodic save for position persistence
            WorldStatePersistence.startPeriodicSave(30000);

            // Start heartbeat for online tracking
            Heartbeat.start();

            if (!silent) Learning.showStageBriefingIfNeeded(State.player.stage);

            // Victory fires ONLY when all 24 companies are fully complete
            if (_allCompaniesComplete()) {
                setTimeout(() => UI.showVictory(State.player), 800);
            }
            return true;
        } catch (e) {
            // Session no longer exists on server -- clean up and let user start fresh
            if (e.message && (e.message.includes('not found') || e.message.includes('404'))) {
                localStorage.removeItem('garage_session_id');
                UI.updateTitleButtons();
                if (!silent) alert('Sessão anterior não encontrada. Inicie um novo jogo.');
            } else {
                if (!silent) alert('Erro ao carregar sessão: ' + e.message);
            }
            return false;
        }
    },

    async enterRegion(regionId, opts = {}) {
        if (!opts.skipPrep) {
            const npcForPrep = NPC_DATA.find(n => n.region === regionId);
            const opened = Learning.showCompanyPrepIfNeeded(regionId, npcForPrep, () => {
                Game.enterRegion(regionId, { skipPrep: true });
            });
            if (opened) return;
        }

        const next = State.challenges.filter(c => c.region === regionId)
            .find(c => !State.player.completed_challenges.includes(c.id));
        if (!next) {
            // All theory challenges done -- check if we need to open IDE
            if (State.lockedRegion === regionId) {
                const npc = NPC_DATA.find(n => n.region === regionId);
                if (npc) {
                    IDE.open(npc);
                    return;
                }
            }
            World.showDialog('SISTEMA', regionId, 'Todos os desafios desta regiao foram completados.');
            return;
        }
        try {
            State.currentChallenge = await API.get('/api/challenges/' + next.id);
            UI.showChallenge(State.currentChallenge);
        } catch (e) { alert('Erro: ' + e.message); }
    },

    async submitAnswer(challengeId, idx) {
        // Guard: prevent double-submit
        const btns = document.querySelectorAll('.option-btn');
        if (btns[idx] && btns[idx].disabled) return;
        btns.forEach(b => b.disabled = true);

        // Guard: already completed on client side
        if (State.player && State.player.completed_challenges &&
            State.player.completed_challenges.includes(challengeId)) {
            UI.hideChallenge();
            return;
        }

        try {
            const r = await API.post('/api/submit', { session_id: State.sessionId, challenge_id: challengeId, selected_index: idx });
            btns[idx].classList.add(r.outcome === 'correct' ? 'correct' : 'wrong');

            if (r.outcome === 'correct') SFX.correct(); else SFX.wrong();

            if (r.outcome === 'game_over') {
                UI.showFeedback(r);
                // Store game_over pending -- user clicks CONTINUAR to see Game Over screen
                State._pendingAfterFeedback = { type: 'game_over', stats: r };
                return;
            }

            UI.showFeedback(r);
            State.player = await API.get('/api/session/' + State.sessionId);
            UI.updateHUD(State.player);

            // After correct theory answer, check if all 3 theory questions for this region are done
            if (r.outcome === 'correct') {
                const theoryChallenge = State.currentChallenge;
                const region = theoryChallenge ? theoryChallenge.region : null;
                const npc = region ? NPC_DATA.find(n => n.region === region) : null;
                // Count how many theory challenges from this region are now completed
                const regionTheoryChallenges = State.challenges.filter(c => c.region === region);
                const completedInRegion = regionTheoryChallenges.filter(c => State.player.completed_challenges.includes(c.id)).length;
                const allTheoryDone = completedInRegion >= regionTheoryChallenges.length;

                // Store pending action so the CONTINUAR button can trigger it
                if (allTheoryDone && npc) {
                    State._pendingAfterFeedback = { type: 'open_ide', npc: npc, promotion: r.promotion ? r : null };
                } else {
                    State._pendingAfterFeedback = { type: 'next_theory', region: region, promotion: r.promotion ? r : null };
                }
            }
        } catch (e) { alert('Erro: ' + e.message); }
    },

    async nextChallenge() {
        const pending = State._pendingAfterFeedback;
        State._pendingAfterFeedback = null;

        if (pending && pending.type === 'game_over') {
            UI.hideChallenge();
            UI.showGameOver(pending.stats);
            return;
        }

        if (pending && pending.type === 'open_ide') {
            // Keep music paused while transitioning from theory to live coding.
            UI.hideChallenge({ resumeMusic: false });
            const openIde = () => IDE.open(pending.npc);
            if (pending.promotion && pending.promotion.new_stage) {
                // All promotions (including Distinguished/CEO) show overlay then open IDE
                UI.showPromotion(pending.promotion.new_stage, pending.promotion.promotion_message, () => {
                    Learning.showStageBriefingIfNeeded(pending.promotion.new_stage, openIde);
                });
                return;
            }
            openIde();
            return;
        }

        if (pending && pending.type === 'next_theory') {
            State.player = await API.get('/api/session/' + State.sessionId);
            State.challenges = await API.get('/api/challenges');
            UI.updateHUD(State.player);
            UI.hideChallenge();
            const continueTheory = () => {
                if (pending.region) Game.enterRegion(pending.region);
            };
            if (pending.promotion && pending.promotion.new_stage) {
                // All promotions (including Distinguished/CEO) show overlay then continue
                UI.showPromotion(pending.promotion.new_stage, pending.promotion.promotion_message, () => {
                    Learning.showStageBriefingIfNeeded(pending.promotion.new_stage, continueTheory);
                });
                return;
            }
            continueTheory();
            return;
        }

        // Fallback: incorrect answer or no pending -- just close
        State.player = await API.get('/api/session/' + State.sessionId);
        State.challenges = await API.get('/api/challenges');
        UI.updateHUD(State.player);
        UI.hideChallenge();
    },

    returnToWorld() { UI.hideChallenge(); },

    async recover() {
        try {
            await API.post('/api/recover', { session_id: State.sessionId });
            State.player = await API.get('/api/session/' + State.sessionId);
            UI.updateHUD(State.player);
            UI.showScreen('screen-world');
        } catch (e) { alert('Erro: ' + e.message); }
    },

    async resetAndReplay() {
        if (!State.sessionId) { location.reload(); return; }
        try {
            // Stop periodic save before reset
            WorldStatePersistence.stopPeriodicSave();
            WorldStatePersistence.reset();
            Heartbeat.stop();

            const data = await API.post('/api/reset', { session_id: State.sessionId });
            State.sessionId = data.session_id;
            State.player = data.player;
            localStorage.setItem('garage_session_id', data.session_id);
            State.challenges = await API.get('/api/challenges');
            Learning.syncSessionState(State.player, State.challenges);
            State._pendingAfterFeedback = null;
            State.currentChallenge = null;
            State.completedRegions = [];
            State.lockedRegion = null;
            State.lockedNpc = null;
            State.doorAnimBuilding = null;
            State.collectedBooks = [];
            World.init(State.avatarIndex || 0, 100);
            UI.updateHUD(State.player);
            UI.showScreen('screen-world');

            // Restart periodic save
            WorldStatePersistence.startPeriodicSave(30000);

            // Restart heartbeat for online tracking
            Heartbeat.start();

            Learning.showStageBriefingIfNeeded(State.player.stage);
        } catch (e) { alert('Erro ao reiniciar: ' + e.message); }
    },

    pause() {
        // Only pause when the world screen is active and not in a challenge/dialog
        const worldActive = document.getElementById('screen-world') &&
            document.getElementById('screen-world').classList.contains('active');
        if (!worldActive) return;
        if (State.isInChallenge || State.isInDialog || State.isBookPopup || State.isInPrep) return;
        if (State.paused) return;

        State.paused = true;
        // Release all movement keys to prevent the player from moving on resume
        if (World.keys) {
            World.keys['ArrowLeft'] = false;
            World.keys['ArrowRight'] = false;
            World.keys['ArrowUp'] = false;
        }
        SFX.pauseMusic();
        const overlay = document.getElementById('pauseOverlay');
        if (overlay) { overlay.style.display = 'flex'; }
    },

    resume() {
        if (!State.paused) return;
        State.paused = false;
        SFX.resumeMusic();
        const overlay = document.getElementById('pauseOverlay');
        if (overlay) { overlay.style.display = 'none'; }
    },
};

// ---- java semantic analyzer (pedagogical compiler sim) ----
const JavaAnalyzer = {

    /**
     * Remove comments and string literals for analysis,
     * preserving line structure for error reporting.
     */
    _stripCommentsAndStrings(code) {
        // 1. Strip string/char literal contents first (keep quotes for structure)
        //    This prevents // or /* inside strings from being treated as comments.
        let stripped = code.replace(/"(?:[^"\\]|\\.)*"/g, '""');
        stripped = stripped.replace(/'(?:[^'\\]|\\.)*'/g, "''");
        // 2. Strip line comments
        stripped = stripped.replace(/\/\/.*$/gm, '');
        // 3. Strip block comments
        stripped = stripped.replace(/\/\*[\s\S]*?\*\//g, '');
        return stripped;
    },

    /**
     * Check balanced braces, parens, brackets.
     * Returns {ok, line, msg} on failure.
     */
    checkBraces(code) {
        const lines = code.split('\n');
        const stack = [];
        const pairs = { '{': '}', '(': ')', '[': ']' };
        const reverse = { '}': '{', ')': '(', ']': '[' };
        let inBlock = false; // track /* */ block comments across lines
        for (let ln = 0; ln < lines.length; ln++) {
            let inStr = false;
            let strChar = null;
            for (let c = 0; c < lines[ln].length; c++) {
                const ch = lines[ln][c];
                // Inside block comment -- skip until */
                if (inBlock) {
                    if (ch === '*' && lines[ln][c + 1] === '/') { inBlock = false; c++; }
                    continue;
                }
                // Inside string/char literal -- skip escaped chars properly
                if (inStr) {
                    if (ch === '\\') { c++; continue; } // skip next char (handles \\, \", \', etc.)
                    if (ch === strChar) inStr = false;
                    continue;
                }
                if (ch === '"' || ch === '\'') { inStr = true; strChar = ch; continue; }
                if (ch === '/' && lines[ln][c + 1] === '/') break; // line comment
                if (ch === '/' && lines[ln][c + 1] === '*') { inBlock = true; c++; continue; } // block comment start
                if (pairs[ch]) stack.push({ ch, line: ln + 1 });
                else if (reverse[ch]) {
                    if (stack.length === 0) return { ok: false, line: ln + 1, msg: 'Erro de compilação: Linha ' + (ln + 1) + ': "' + ch + '" sem abertura correspondente.' };
                    const top = stack.pop();
                    if (pairs[top.ch] !== ch) return { ok: false, line: ln + 1, msg: 'Erro de compilação: Linha ' + (ln + 1) + ': esperava "' + pairs[top.ch] + '" mas encontrou "' + ch + '". Abertura na linha ' + top.line + '.' };
                }
            }
        }
        if (stack.length > 0) {
            const top = stack[stack.length - 1];
            return { ok: false, line: top.line, msg: 'Erro de compilação: "' + top.ch + '" aberto na linha ' + top.line + ' nunca foi fechado. Falta "' + pairs[top.ch] + '".' };
        }
        return { ok: true };
    },

    /**
     * Check semicolons on statement lines.
     * Skips lines with { } class/method/if/for/while/else headers.
     */
    checkSemicolons(code) {
        const lines = code.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line || line.startsWith('//') || line.startsWith('/*') || line.startsWith('*')) continue;
            if (line.startsWith('@')) continue; // annotations (@Override, @SuppressWarnings, etc.)
            if (line === '{' || line === '}' || line === '};' || line === '},' || line.endsWith('{') || line.endsWith('}')) continue;
            if (/^(public|private|protected|static|class|interface|enum|if|else|for|while|do|switch|case|default|try|catch|finally|import|package)\b/.test(line) && line.endsWith('{')) continue;
            // Control flow headers without { on same line: if (...), for (...), while (...), catch (...)
            if (/^(if|for|while|catch)\s*\(/.test(line) && line.endsWith(')')) continue;
            if (/^(else|do|try|finally)\s*$/.test(line)) continue;
            if (/^\}\s*(else|catch|finally)/.test(line)) continue;
            if (/^\}/.test(line)) continue;
            if (/^(import|package)\s/.test(line) && !line.endsWith(';'))
                return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': falta ";" no final da declaracao.' };
            // Statement lines (assignments, method calls, return, declarations)
            if (/^(int|long|double|float|char|boolean|String|var|return|System|HashMap|HashSet|Stack|Queue|LinkedList|ListNode|TreeNode|PriorityQueue|ArrayList|Map|List|Set)\b/.test(line) ||
                /^\w+\s*[\.\[\(=<]/.test(line) ||
                /^\w+\s*<(?:[^<>]*(?:<[^<>]*>)?)*>\s+\w+\s*=/.test(line) ||
                /^\w+\s+\w+\s*=/.test(line)) {
                if (!line.endsWith(';') && !line.endsWith('{') && !line.endsWith('}') && !line.endsWith(',') && !line.endsWith('(') && !/\)\s*\{/.test(line))
                    return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': falta ";" no final da declaracao.' };
            }
        }
        return { ok: true };
    },

    /**
     * Extract all declared variable names with types from the code.
     * Returns Map<name, {type, line}>.
     */
    extractDeclarations(code) {
        const decls = new Map();
        const lines = code.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            // Typical: int x = ...; | int[] arr = ...; | String s = ...; | Type<Gen> v = ...;
            // Also: for (int i = 0; ...)
            const patterns = [
                /\b(int|long|double|float|char|boolean|String|byte|short)\s*(\[\s*\])?\s+(\w+)\s*[=;,)]/,
                /\b(HashMap|Map|Stack|Queue|LinkedList|List|ArrayList|Set|HashSet|TreeMap|PriorityQueue|Deque|ArrayDeque|TreeSet)\s*<(?:[^<>]*(?:<[^<>]*>)?)*>\s+(\w+)\s*[=;]/,
                /\b(ListNode|TreeNode)\s+(\w+)\s*[=;]/,
                /\b([A-Z]\w+)\s+(\w+)\s*[=;]/,
            ];
            for (const pat of patterns) {
                const matches = line.matchAll(new RegExp(pat.source, 'g'));
                for (const m of matches) {
                    const name = m[3] || m[2];
                    if (name && !decls.has(name)) {
                        decls.set(name, { type: m[1], line: i + 1 });
                    }
                }
            }
            // For loop declarations: for (int i = 0; ...)
            const forMatch = line.match(/for\s*\(\s*(int|long)\s+(\w+)\s*=/);
            if (forMatch) {
                const name = forMatch[2];
                if (!decls.has(name)) decls.set(name, { type: forMatch[1], line: i + 1 });
            }
            // For-each: for (int n : arr) or for (Type<Gen> n : collection.method())
            const forEachMatch = line.match(/for\s*\(\s*([\w.]+(?:<(?:[^<>]*(?:<[^<>]*>)?)*>)?(?:\[\s*\])?)\s+(\w+)\s*:\s*[^)]+\)/);
            if (forEachMatch) {
                if (!decls.has(forEachMatch[2])) decls.set(forEachMatch[2], { type: forEachMatch[1], line: i + 1 });
            }
        }
        return decls;
    },

    /**
     * Validate for-loop semantics:
     * - Iterator variable must be declared (in for-init or prior)
     * - Condition must reference the same iterator
     * - .length must reference a declared array variable
     * - Loop body must use the iterator for array access
     */
    checkForLoop(code, decls) {
        const lines = code.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();

            // Standard for loop
            const forMatch = line.match(/for\s*\(\s*(?:int\s+)?(\w+)\s*=\s*[^;]+;\s*(\w+)\s*(<|<=|>|>=|!=)\s*([^;]+);\s*([^)]+)\)/);
            if (forMatch) {
                const initVar = forMatch[1];
                const condVar = forMatch[2];
                const condExpr = forMatch[4].trim();
                const incrExpr = forMatch[5].trim();

                // Check: init var must match condition var
                if (initVar !== condVar) {
                    return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': variável do inicializador "' + initVar + '" é diferente da variável na condição "' + condVar + '". O for espera a mesma variável.' };
                }

                // Check: increment must reference the same var
                if (!incrExpr.includes(initVar)) {
                    return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': incremento "' + incrExpr + '" não usa a variável iteradora "' + initVar + '".' };
                }

                // Check: if condition references .length, the object must be declared
                // Use negative lookahead to skip .length() method calls (String/Collection)
                const lengthMatch = condExpr.match(/(\w+)\.length(?!\s*\()/);
                if (lengthMatch) {
                    const arrName = lengthMatch[1];
                    if (!decls.has(arrName)) {
                        return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': variável "' + arrName + '" não foi declarada. Você quis dizer outra variável?' };
                    }
                }

                // Check: init var name must not shadow an existing array
                if (decls.has(initVar)) {
                    const existing = decls.get(initVar);
                    // If the "declaration" is an array but we're re-declaring as int in for-init
                    const forDeclMatch = line.match(/for\s*\(\s*int\s+(\w+)/);
                    if (!forDeclMatch) {
                        // Not declaring in for-init, check the var exists
                        // ok
                    }
                }

                // Check: if declaring int with same name as an existing array in scope
                const forDeclMatch = line.match(/for\s*\(\s*int\s+(\w+)/);
                if (forDeclMatch) {
                    const declName = forDeclMatch[1];
                    if (decls.has(declName)) {
                        const prev = decls.get(declName);
                        // Same name as array = shadowing error
                        if (prev.type === 'int' && prev.line < i + 1) {
                            // Could be a re-declaration issue, but for simple scope, warn about array collision
                        }
                    }
                }
            }
        }
        return { ok: true };
    },

    /**
     * Validate println/print arguments reference declared variables.
     */
    checkPrintStatements(code, decls) {
        const lines = code.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            // Greedy regex: captures full argument including nested parens (requires trailing ;)
            let printMatch = line.match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\((.*)\)\s*;/);
            // Fallback for lines without ; (already caught by semicolon check, just skip gracefully)
            if (!printMatch) {
                printMatch = line.match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\(([^)]*)\)/);
            }
            if (printMatch) {
                const arg = printMatch[1].trim();
                if (!arg) {
                    // Empty println() -- only valid as blank line print, but flag if inside a loop iterating an array
                    const contextAbove = lines.slice(Math.max(0, i - 5), i).join('\n');
                    if (/for\s*\(/.test(contextAbove) && decls.size > 0) {
                        // Inside or near a for loop -- empty println is likely wrong
                        return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': System.out.println() sem argumento. Você provavelmente deveria imprimir um elemento do array. Ex: System.out.println(arr[i]);' };
                    }
                    continue;
                }
                // Check if arg references undeclared variables (basic check)
                // Extract variable references from the argument (skip strings and numbers)
                const cleanArg = arg.replace(/"[^"]*"/g, '').replace(/\b\d+\b/g, '').replace(/\.\w+/g, '').trim();
                if (cleanArg) {
                    const varRefs = cleanArg.match(/\b[a-zA-Z_]\w*\b/g) || [];
                    const javaKeywords = new Set(['new', 'null', 'true', 'false', 'this', 'super', 'instanceof', 'return', 'if', 'else', 'for', 'while', 'int', 'long', 'double', 'float', 'char', 'boolean', 'byte', 'short', 'void', 'class', 'static', 'public', 'private', 'protected', 'final', 'abstract', 'extends', 'implements', 'throw', 'throws', 'try', 'catch', 'break', 'continue', 'switch', 'case', 'default', 'do']);
                    const javaClasses = new Set(['System', 'String', 'Integer', 'Double', 'Math', 'Arrays', 'Map', 'Entry', 'Character', 'HashMap', 'HashSet', 'LinkedList', 'ArrayList', 'Stack', 'Queue', 'PriorityQueue', 'TreeMap', 'TreeSet', 'List', 'Set', 'Collections', 'Objects', 'Comparable', 'Comparator', 'Object', 'Boolean', 'Long', 'Float', 'Byte', 'Short']);
                    const javaMethods = new Set(['toString', 'valueOf', 'parseInt', 'getKey', 'getValue', 'size', 'length', 'charAt', 'format', 'isEmpty', 'pop', 'push', 'poll', 'peek', 'get', 'containsKey', 'entrySet', 'add', 'remove', 'contains', 'put', 'of', 'asList', 'sort', 'toCharArray', 'toLowerCase', 'toUpperCase', 'replaceAll', 'substring', 'trim', 'equals', 'compareTo', 'getOrDefault', 'addFirst', 'removeLast', 'offer', 'compare']);
                    // Extract user-defined method names from the code (static/non-static)
                    const userMethods = new Set();
                    const methodDeclRe = /\b(?:static\s+)?(?:void|int|long|double|float|char|boolean|String|int\[\]|String\[\]|[A-Z]\w*(?:<(?:[^<>]*(?:<[^<>]*>)?)*>)?(?:\[\])?)\s+(\w+)\s*\(/g;
                    let mm;
                    while ((mm = methodDeclRe.exec(code)) !== null) { userMethods.add(mm[1]); }
                    for (const ref of varRefs) {
                        if (javaKeywords.has(ref) || javaClasses.has(ref) || javaMethods.has(ref)) continue;
                        // Skip if this identifier is a method call (followed by parenthesis)
                        if (new RegExp('\\b' + ref + '\\s*\\(').test(arg)) continue;
                        // Skip user-defined method names
                        if (userMethods.has(ref)) continue;
                        // Check method params (rough: check if method signature has this var)
                        const methodParam = code.match(new RegExp('(?:\\(|,)\\s*(?:int\\[\\]|int|String|long|double|boolean|float|char|byte|short|String\\[\\]|[A-Z]\\w*(?:<(?:[^<>]*(?:<[^<>]*>)?)*>)?(?:\\[\\])?)\\s+' + ref + '\\b'));
                        if (methodParam) continue;
                        if (!decls.has(ref)) {
                            return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': variável "' + ref + '" não foi declarada neste escopo.' };
                        }
                    }
                }
            }
        }
        return { ok: true };
    },

    /**
     * Check for common for-loop array access issues:
     * - Using array name as iterator: for(int nums = 0; ...)
     * - Iterator used with wrong array in body
     */
    checkArrayForCoherence(code) {
        const stripped = this._stripCommentsAndStrings(code);
        const lines = stripped.split('\n');

        // Find array declarations
        const arrayDecls = [];
        for (let i = 0; i < lines.length; i++) {
            // Local declarations: int[] arr = ...;
            const m = lines[i].match(/\b(int|long|double|float|String|char)\s*\[\s*\]\s+(\w+)\s*=/);
            if (m) arrayDecls.push({ name: m[2], type: m[1], line: i + 1 });
            // Method parameters: (int[] nums, int target) or (String[] args)
            const paramRe = /\b(int|long|double|float|String|char)\s*\[\s*\]\s+(\w+)\s*[,)]/g;
            let pm;
            while ((pm = paramRe.exec(lines[i])) !== null) {
                if (!arrayDecls.some(a => a.name === pm[2])) {
                    arrayDecls.push({ name: pm[2], type: pm[1], line: i + 1 });
                }
            }
        }

        // Check for-loops that iterate arrays
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            const forMatch = line.match(/for\s*\(\s*(?:int\s+)?(\w+)\s*=/);
            if (!forMatch) continue;
            const iterName = forMatch[1];

            // If iterator name matches an existing array name -- critical error
            for (const arr of arrayDecls) {
                if (iterName === arr.name) {
                    return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': você está usando "' + iterName + '" como iterador do for, mas "' + iterName + '" já é o nome do seu array (declarado na linha ' + arr.line + '). Use um nome diferente para o contador, como "i". Ex: for (int i = 0; i < ' + arr.name + '.length; i++)' };
                }
            }

            // Check condition uses a declared array for .length (skip .length() method calls)
            const condMatch = line.match(/(\w+)\.length(?!\s*\()/);
            if (condMatch) {
                const condArr = condMatch[1];
                const knownArr = arrayDecls.find(a => a.name === condArr);
                if (!knownArr && condArr !== 'args') {
                    // Check if they wrote the wrong name
                    if (arrayDecls.length > 0) {
                        return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': "' + condArr + '.length" -- variável "' + condArr + '" não existe. O array se chama "' + arrayDecls[0].name + '". Use: ' + arrayDecls[0].name + '.length' };
                    }
                    return { ok: false, line: i + 1, msg: 'Erro de compilação: Linha ' + (i + 1) + ': "' + condArr + '" não é uma variável declarada.' };
                }
            }

            // Check body: if println is inside the loop, it should access array[iterator]
            // Scan lines after the for until matching closing brace
            let braceCount = 0;
            let loopStarted = false;
            for (let j = i; j < lines.length; j++) {
                for (const ch of lines[j]) {
                    if (ch === '{') { braceCount++; loopStarted = true; }
                    if (ch === '}') braceCount--;
                }
                if (loopStarted && braceCount <= 0) break;
                if (j > i || loopStarted) {
                    const printMatch = lines[j].match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\(\s*\)/);
                    if (printMatch && arrayDecls.length > 0) {
                        return { ok: false, line: j + 1, msg: 'Erro de compilação: Linha ' + (j + 1) + ': System.out.println() está vazio dentro do loop. Para imprimir elementos do array, use: System.out.println(' + arrayDecls[0].name + '[' + iterName + ']);' };
                    }
                    // Check if println uses array[wrong_var]
                    const printArrMatch = lines[j].match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\(\s*(\w+)\s*\[\s*(\w+)\s*\]\s*\)/);
                    if (printArrMatch) {
                        const usedArr = printArrMatch[1];
                        const usedIdx = printArrMatch[2];
                        const knownArr = arrayDecls.find(a => a.name === usedArr);
                        if (!knownArr) {
                            return { ok: false, line: j + 1, msg: 'Erro de compilação: Linha ' + (j + 1) + ': array "' + usedArr + '" não foi declarado.' };
                        }
                        // Extract iterator declared in for-init
                        const forDeclMatch = line.match(/for\s*\(\s*int\s+(\w+)/);
                        const actualIter = forDeclMatch ? forDeclMatch[1] : iterName;
                        if (usedIdx !== actualIter) {
                            return { ok: false, line: j + 1, msg: 'Erro de compilação: Linha ' + (j + 1) + ': índice "' + usedIdx + '" não foi declarado neste escopo. O iterador do for é "' + actualIter + '". Use: ' + usedArr + '[' + actualIter + ']' };
                        }
                    }
                }
            }
        }
        return { ok: true };
    },

    /**
     * Master analysis pipeline. Runs all checks in order.
     * Returns {ok:true} or {ok:false, msg:string, line:number}.
     */
    analyze(code) {
        // Phase 1: Structural -- braces
        const braces = this.checkBraces(code);
        if (!braces.ok) return braces;

        // Phase 2: Semicolons
        const semis = this.checkSemicolons(code);
        if (!semis.ok) return semis;

        // Phase 3: Extract declarations
        const decls = this.extractDeclarations(code);

        // Phase 4: For-loop / array coherence
        const arrCheck = this.checkArrayForCoherence(code);
        if (!arrCheck.ok) return arrCheck;

        // Phase 5: For-loop variable semantics
        const forCheck = this.checkForLoop(code, decls);
        if (!forCheck.ok) return forCheck;

        // Phase 6: Print statement references
        const printCheck = this.checkPrintStatements(code, decls);
        if (!printCheck.ok) return printCheck;

        return { ok: true };
    },
};

// ---- IDE coding challenges ----

/**
 * Progressive code challenges per stage.
 * Each entry: id, stage, region, title, description, concept, language,
 *   fileName, starterCode, validator (function), helpMentor, helpText.
 * Validator receives trimmed user code string, returns {ok, msg}.
 *
 * ARCHITECTURE: Each validator calls JavaAnalyzer.analyze() first for
 * structural/semantic compilation checks. Only if the code passes compilation
 * does the validator proceed to domain-specific (pedagogical) checks.
 * This ensures: if javac would reject, the IDE also rejects.
 */
const CODE_CHALLENGES = [
    // ── INTERN ──────────────────────────────────────────────────────────────
    {
        id: 'code_hello', stage: 'Intern', region: 'Xerox PARC',
        title: 'Hello World', concept: 'Syntax / Estrutura básica',
        language: 'java', fileName: 'HelloWorld.java',
        description: 'Escreva a classe HelloWorld com o método main que imprime "Hello World" no console.\n\nRegras:\n- Nome da classe: HelloWorld (CamelCase)\n- Método: public static void main(String[] args)\n- Saída: System.out.println("Hello World");',
        starterCode: '// Escreva sua classe aqui\n\n',
        validator(code) {
            // Phase 1: Structural compilation
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            // Phase 2: Domain-specific checks
            if (!/class\s+HelloWorld\b/.test(code)) {
                const classMatch = code.match(/class\s+(\w+)/);
                if (classMatch) {
                    const typed = classMatch[1];
                    if (/^hello\s*world$/i.test(typed)) return { ok: false, msg: 'Erro de compilação: Java e case-sensitive. Use HelloWorld (H e W maiusculos).' };
                    if (typed.toLowerCase().includes('hello')) return { ok: false, msg: 'Erro de compilação: Nome da classe incorreto: "' + typed + '". Deve ser exatamente HelloWorld.' };
                    return { ok: false, msg: 'Erro de compilação: A classe deve se chamar HelloWorld (CamelCase). Você escreveu: ' + typed };
                }
                return { ok: false, msg: 'Erro de compilação: Falta declarar a classe. Use: public class HelloWorld { ... }' };
            }
            if (!/public\s+static\s+void\s+main\s*\(\s*String\s*\[\s*\]\s+\w+\s*\)/.test(code)) return { ok: false, msg: 'Erro de compilação: Método main incorreto. Use: public static void main(String[] args)' };
            if (!/System\s*\.\s*out\s*\.\s*println\s*\(\s*"Hello World[!]?"\s*\)/.test(code)) {
                if (/system\s*\.\s*out/i.test(code) && !/System\.out/.test(code)) return { ok: false, msg: 'Erro de compilação: Java e case-sensitive. Use System.out.println (S maiusculo).' };
                if (/System\s*\.\s*out\s*\.\s*print\s*\(/.test(code) && !/println/.test(code)) return { ok: false, msg: 'Erro de compilação: Use println (com "ln" no final), não print.' };
                if (/"hello world"/i.test(code) && !/"Hello World"/.test(code)) return { ok: false, msg: 'Erro de compilação: O texto deve ser exatamente "Hello World" (H e W maiusculos).' };
                return { ok: false, msg: 'Erro de compilação: Use System.out.println("Hello World");' };
            }
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Hello World\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Todo programa Java começa com uma classe\n2. O ponto de entrada é o método main (assinatura fixa)\n3. System.out.println() é a função de saída\n\nCOLA -- Copie este código na IDE:\n\npublic class HelloWorld {\n    public static void main(String[] args) {\n        System.out.println("Hello World");\n    }\n}'
    },
    {
        id: 'code_var', stage: 'Intern', region: 'Apple Garage',
        title: 'Variáveis e Tipos', concept: 'Tipos primitivos / Declaração',
        language: 'java', fileName: 'Variables.java',
        description: 'Declare e imprima:\n1. int idade = 20;\n2. double salario = 3500.50;\n3. String nome = "Dev";\n4. boolean ativo = true;\n\nImprima cada variável com System.out.println().',
        starterCode: 'public class Variables {\n    public static void main(String[] args) {\n        // Declare suas variáveis aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Variables/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar Variables.' };
            if (!/int\s+\w+\s*=\s*\d+/.test(code)) return { ok: false, msg: 'Erro de compilação: Declare uma variável int. Ex: int idade = 20;' };
            if (!/double\s+\w+\s*=\s*[\d.]+/.test(code)) return { ok: false, msg: 'Erro de compilação: Declare uma variável double. Ex: double salario = 3500.50;' };
            if (!/String\s+\w+\s*=\s*"[^"]*"/.test(code)) return { ok: false, msg: 'Erro de compilação: Declare uma variável String. Ex: String nome = "Dev";' };
            if (!/boolean\s+\w+\s*=\s*(true|false)/.test(code)) return { ok: false, msg: 'Erro de compilação: Declare uma variável boolean. Ex: boolean ativo = true;' };
            const printCount = (code.match(/System\s*\.\s*out\s*\.\s*println/g) || []).length;
            if (printCount < 4) return { ok: false, msg: 'Erro semântico: Imprima cada variavel com System.out.println(). Faltam ' + (4 - printCount) + ' prints.' };
            // Verify println arguments reference declared vars
            const declNames = [];
            const declMatches = code.matchAll(/\b(int|double|String|boolean)\s+(\w+)\s*=/g);
            for (const m of declMatches) declNames.push(m[2]);
            const printArgs = code.matchAll(/System\s*\.\s*out\s*\.\s*println\s*\(\s*(\w+)\s*\)/g);
            for (const m of printArgs) {
                if (!declNames.includes(m[1]) && m[1] !== 'true' && m[1] !== 'false')
                    return { ok: false, msg: 'Erro de compilação: variável "' + m[1] + '" no println não foi declarada.' };
            }
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 20\n> 3500.5\n> Dev\n> true\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Java tem 4 tipos básicos: int (inteiro), double (decimal), String (texto), boolean (true/false)\n2. Cada variável precisa de tipo + nome + valor\n3. Ponto e vírgula no final de cada linha\n\nCOLA -- Copie este código na IDE:\n\npublic class Variables {\n    public static void main(String[] args) {\n        int idade = 20;\n        double salario = 3500.50;\n        String nome = "Dev";\n        boolean ativo = true;\n\n        System.out.println(idade);\n        System.out.println(salario);\n        System.out.println(nome);\n        System.out.println(ativo);\n    }\n}'
    },
    // ── JUNIOR ──────────────────────────────────────────────────────────────
    {
        id: 'code_array', stage: 'Junior', region: 'Microsoft',
        title: 'Array e Loop', concept: 'Arrays / Iteração',
        language: 'java', fileName: 'ArrayLoop.java',
        description: 'Crie um array de inteiros {10, 20, 30, 40, 50}.\nUse um loop for para imprimir cada elemento.\n\nDica: array.length retorna o tamanho.',
        starterCode: 'public class ArrayLoop {\n    public static void main(String[] args) {\n        // Crie o array e o loop aqui\n\n    }\n}\n',
        validator(code) {
            // Phase 1: Structural + semantic compilation
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            // Phase 2: Domain checks
            if (!/class\s+ArrayLoop/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar ArrayLoop.' };
            if (!/int\s*\[\s*\]\s+\w+\s*=\s*\{/.test(code) && !/int\s*\[\s*\]\s+\w+\s*=\s*new\s+int/.test(code))
                return { ok: false, msg: 'Erro de compilação: Declare um array de int. Ex: int[] nums = {10, 20, 30, 40, 50};' };
            // Extract array name
            const arrMatch = code.match(/int\s*\[\s*\]\s+(\w+)\s*=/);
            const arrName = arrMatch ? arrMatch[1] : 'nums';
            // Must have a for loop
            if (!/for\s*\(/.test(code) && !/for\s*\(\s*int\s+\w+\s*:/.test(code))
                return { ok: false, msg: 'Erro de compilação: Use um loop for para iterar o array.' };
            // Check for-each or standard for
            const forEachMatch = code.match(/for\s*\(\s*int\s+(\w+)\s*:\s*(\w+)\s*\)/);
            if (forEachMatch) {
                // For-each: verify array name matches
                if (forEachMatch[2] !== arrName)
                    return { ok: false, msg: 'Erro de compilação: for-each itera sobre "' + forEachMatch[2] + '" mas o array se chama "' + arrName + '".' };
                // Verify println uses the loop variable
                const loopVar = forEachMatch[1];
                const printInLoop = new RegExp('System\\s*\\.\\s*out\\s*\\.\\s*println\\s*\\(\\s*' + loopVar + '\\s*\\)');
                if (!printInLoop.test(code))
                    return { ok: false, msg: 'Erro semântico: Dentro do for-each, imprima a variavel "' + loopVar + '". Ex: System.out.println(' + loopVar + ');' };
            } else {
                // Standard for: verify .length references correct array
                if (!/\.length/.test(code)) return { ok: false, msg: 'Erro semântico: Use ' + arrName + '.length como condicao do for.' };
                const lengthRef = code.match(/(\w+)\.length(?!\s*\()/);
                if (lengthRef && lengthRef[1] !== arrName && lengthRef[1] !== 'args')
                    return { ok: false, msg: 'Erro de compilação: "' + lengthRef[1] + '.length" -- variável "' + lengthRef[1] + '" não existe. O array se chama "' + arrName + '". Use: ' + arrName + '.length' };
                // Verify println accesses array[i]
                const printArrAccess = new RegExp('System\\s*\\.\\s*out\\s*\\.\\s*println\\s*\\(\\s*' + arrName + '\\s*\\[\\s*\\w+\\s*\\]\\s*\\)');
                if (!printArrAccess.test(code))
                    return { ok: false, msg: 'Erro semântico: Imprima cada elemento com System.out.println(' + arrName + '[i]); dentro do loop.' };
            }
            if (!/System\s*\.\s*out\s*\.\s*println/.test(code)) return { ok: false, msg: 'Erro de compilação: Use System.out.println() para imprimir.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 10\n> 20\n> 30\n> 40\n> 50\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Array = coleção de tamanho fixo. Índices começam em 0.\n2. Loop for: inicialização; condição; incremento\n3. i < array.length garante que não acessa fora dos limites\n\nCOLA -- Copie este código na IDE:\n\npublic class ArrayLoop {\n    public static void main(String[] args) {\n        int[] nums = {10, 20, 30, 40, 50};\n\n        for (int i = 0; i < nums.length; i++) {\n            System.out.println(nums[i]);\n        }\n    }\n}'
    },
    {
        id: 'code_fizzbuzz', stage: 'Junior', region: 'Nubank',
        title: 'FizzBuzz', concept: 'Condicional / Módulo',
        language: 'java', fileName: 'FizzBuzz.java',
        description: 'Implemente FizzBuzz de 1 a 15:\n- Múltiplo de 3 e 5: imprima "FizzBuzz"\n- Múltiplo de 3: imprima "Fizz"\n- Múltiplo de 5: imprima "Buzz"\n- Caso contrário: imprima o número\n\nPENSE ANTES: a ordem dos if/else importa!',
        starterCode: 'public class FizzBuzz {\n    public static void main(String[] args) {\n        for (int i = 1; i <= 15; i++) {\n            // Sua logica aqui\n\n        }\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+FizzBuzz/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar FizzBuzz.' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use um loop for.' };
            if (!/%\s*3/.test(code) || !/%\s*5/.test(code)) return { ok: false, msg: 'Erro semântico: Use o operador módulo (%). Ex: i % 3 == 0' };
            if (!/if\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use if/else para as condições.' };
            if (!/"FizzBuzz"/.test(code)) return { ok: false, msg: 'Erro semântico: Quando múltiplo de 3 E 5, imprima "FizzBuzz".' };
            if (!/"Fizz"/.test(code)) return { ok: false, msg: 'Erro semântico: Quando múltiplo de 3, imprima "Fizz".' };
            if (!/"Buzz"/.test(code)) return { ok: false, msg: 'Erro semântico: Quando múltiplo de 5, imprima "Buzz".' };
            // Verify FizzBuzz check comes BEFORE individual Fizz/Buzz
            const fbPos = code.indexOf('FizzBuzz');
            const fPos = code.indexOf('"Fizz"');
            const bPos = code.indexOf('"Buzz"');
            if (fbPos > fPos || fbPos > bPos)
                return { ok: false, msg: 'Erro lógico: A condição "FizzBuzz" (múltiplo de 3 E 5) DEVE vir ANTES das condições individuais "Fizz" e "Buzz". Caso contrário, 15 nunca será FizzBuzz.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 1\n> 2\n> Fizz\n> 4\n> Buzz\n> Fizz\n> 7\n> 8\n> Fizz\n> Buzz\n> 11\n> Fizz\n> 13\n> 14\n> FizzBuzz\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. A ORDEM importa: teste "múltiplo de 3 E 5" PRIMEIRO\n2. Se testar "múltiplo de 3" antes, 15 imprime "Fizz" ao invés de "FizzBuzz"\n3. Operador %: a % b retorna o RESTO da divisão. Se resto == 0, é múltiplo.\n\nCOLA -- Copie este código na IDE:\n\npublic class FizzBuzz {\n    public static void main(String[] args) {\n        for (int i = 1; i <= 15; i++) {\n            if (i % 3 == 0 && i % 5 == 0) {\n                System.out.println("FizzBuzz");\n            } else if (i % 3 == 0) {\n                System.out.println("Fizz");\n            } else if (i % 5 == 0) {\n                System.out.println("Buzz");\n            } else {\n                System.out.println(i);\n            }\n        }\n    }\n}'
    },
    // ── MID ─────────────────────────────────────────────────────────────────
    {
        id: 'code_stack', stage: 'Mid', region: 'Google',
        title: 'Pilha (Stack)', concept: 'Estrutura de dados LIFO',
        language: 'java', fileName: 'StackDemo.java',
        description: 'Use java.util.Stack para:\n1. Criar uma Stack<Integer>\n2. Fazer push de 10, 20, 30\n3. Fazer pop e imprimir o topo\n4. Imprimir o tamanho final com size()',
        starterCode: 'import java.util.Stack;\n\npublic class StackDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.Stack/.test(code)) return { ok: false, msg: 'Erro de compilação: Falta import java.util.Stack;' };
            if (!/Stack\s*<\s*Integer\s*>\s+\w+\s*=\s*new\s+Stack/.test(code)) return { ok: false, msg: 'Erro de compilação: Crie a Stack: Stack<Integer> stack = new Stack<>();' };
            if (!(/\.push\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use stack.push() para adicionar elementos.' };
            if (!(/\.pop\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use stack.pop() para remover o topo.' };
            if (!(/\.size\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use stack.size() para imprimir o tamanho.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Pop: 30\n> Tamanho: 2\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Stack = LIFO (Last In, First Out). O último a entrar sai primeiro.\n2. Analogia: pilha de pratos. Você só tira o de cima.\n3. push() coloca no topo, pop() remove do topo, peek() vê sem remover.\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.Stack;\n\npublic class StackDemo {\n    public static void main(String[] args) {\n        Stack<Integer> stack = new Stack<>();\n        stack.push(10);\n        stack.push(20);\n        stack.push(30);\n\n        int topo = stack.pop();\n        System.out.println("Pop: " + topo);\n        System.out.println("Tamanho: " + stack.size());\n    }\n}'
    },
    {
        id: 'code_linkedlist', stage: 'Mid', region: 'Facebook',
        title: 'LinkedList', concept: 'Lista encadeada / Inserção O(1)',
        language: 'java', fileName: 'LinkedListDemo.java',
        description: 'Use java.util.LinkedList para:\n1. Criar LinkedList<String>\n2. Adicionar "Alpha", "Beta", "Gamma" com add()\n3. Adicionar "First" no início com addFirst()\n4. Remover o último com removeLast()\n5. Imprimir a lista',
        starterCode: 'import java.util.LinkedList;\n\npublic class LinkedListDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilação: Falta import java.util.LinkedList;' };
            if (!/LinkedList\s*<\s*String\s*>\s+\w+\s*=\s*new\s+LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilação: Crie: LinkedList<String> list = new LinkedList<>();' };
            if (!(/\.add\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use list.add() para adicionar elementos.' };
            if (!(/\.addFirst\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use list.addFirst() para inserir no início.' };
            if (!(/\.removeLast\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use list.removeLast() para remover o último.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [First, Alpha, Beta]\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. LinkedList = nós conectados por ponteiros. Inserção no início/fim é O(1).\n2. Diferente de ArrayList: não tem acesso aleatório O(1), mas inserção/remoção nas pontas é instantânea.\n3. addFirst() insere antes do primeiro nó, removeLast() remove o último.\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.LinkedList;\n\npublic class LinkedListDemo {\n    public static void main(String[] args) {\n        LinkedList<String> list = new LinkedList<>();\n        list.add("Alpha");\n        list.add("Beta");\n        list.add("Gamma");\n        list.addFirst("First");\n        list.removeLast();\n        System.out.println(list);\n    }\n}'
    },
    // ── SENIOR ──────────────────────────────────────────────────────────────
    {
        id: 'code_hashmap', stage: 'Senior', region: 'Amazon',
        title: 'HashMap', concept: 'Hash table / O(1) lookup',
        language: 'java', fileName: 'HashMapDemo.java',
        description: 'Use java.util.HashMap para:\n1. Criar HashMap<String, Integer>\n2. Inserir: "Java"->1995, "Python"->1991, "Go"->2009\n3. Verificar se contém "Java" com containsKey()\n4. Obter valor de "Python" com get()\n5. Iterar com entrySet() e imprimir chave=valor',
        starterCode: 'import java.util.HashMap;\nimport java.util.Map;\n\npublic class HashMapDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.HashMap/.test(code)) return { ok: false, msg: 'Erro de compilação: Falta import java.util.HashMap;' };
            if (!/(?:Map|HashMap)\s*<\s*String\s*,\s*Integer\s*>/.test(code)) return { ok: false, msg: 'Erro de compilação: Crie: Map<String, Integer> map = new HashMap<>();' };
            if (!(/\.put\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use map.put("key", value) para inserir.' };
            if (!(/\.containsKey\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use map.containsKey("Java") para verificar.' };
            if (!(/\.get\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use map.get("Python") para obter valor.' };
            if (!/\.entrySet\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use map.entrySet() para obter os pares chave-valor.' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Itere com for (Map.Entry<> e : map.entrySet())' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Contem Java: true\n> Python: 1991\n> Java=1995\n> Python=1991\n> Go=2009\n\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. HashMap = tabela hash. Armazena pares chave-valor.\n2. Busca por chave é O(1) -- constante, não importa quantos elementos.\n3. put() insere, get() busca, containsKey() verifica existência.\n4. entrySet() retorna todos os pares para iteração.\n5. Declare usando a interface Map<> (programe para a interface, não a implementação).\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.HashMap;\nimport java.util.Map;\n\npublic class HashMapDemo {\n    public static void main(String[] args) {\n        Map<String, Integer> map = new HashMap<>();\n        map.put("Java", 1995);\n        map.put("Python", 1991);\n        map.put("Go", 2009);\n\n        System.out.println("Contem Java: " + map.containsKey("Java"));\n        System.out.println("Python: " + map.get("Python"));\n\n        for (Map.Entry<String, Integer> e : map.entrySet()) {\n            System.out.println(e.getKey() + "=" + e.getValue());\n        }\n    }\n}'
    },
    {
        id: 'code_queue', stage: 'Senior', region: 'Mercado Livre',
        title: 'Fila (Queue)', concept: 'Estrutura FIFO / Processamento de pedidos',
        language: 'java', fileName: 'QueueDemo.java',
        description: 'Simule uma fila de pedidos do Mercado Livre:\n1. Criar Queue<String> usando LinkedList\n2. Enfileirar: "Pedido-001", "Pedido-002", "Pedido-003"\n3. Processar (poll) e imprimir cada pedido\n4. Mostrar se a fila está vazia com isEmpty()',
        starterCode: 'import java.util.Queue;\nimport java.util.LinkedList;\n\npublic class QueueDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.Queue/.test(code)) return { ok: false, msg: 'Erro de compilação: Falta import java.util.Queue;' };
            if (!/Queue\s*<\s*String\s*>\s+\w+\s*=\s*new\s+LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilação: Crie: Queue<String> fila = new LinkedList<>();' };
            if (!(/\.(add|offer)\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use fila.add() ou fila.offer() para enfileirar.' };
            if (!(/\.poll\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use fila.poll() para processar o próximo da fila.' };
            if (!(/\.isEmpty\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use fila.isEmpty() para verificar se esta vazia.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Processando: Pedido-001\n> Processando: Pedido-002\n> Processando: Pedido-003\n> Fila vazia: true\n\nFIFO: primeiro pedido a entrar e o primeiro a ser processado.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Queue = FIFO (First In, First Out). Primeiro a entrar, primeiro a sair.\n2. Analogia: fila de supermercado. Quem chegou primeiro é atendido primeiro.\n3. offer()/add() coloca no fim, poll() remove do início.\n4. Queue é interface, LinkedList é a implementação.\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.Queue;\nimport java.util.LinkedList;\n\npublic class QueueDemo {\n    public static void main(String[] args) {\n        Queue<String> fila = new LinkedList<>();\n        fila.add("Pedido-001");\n        fila.add("Pedido-002");\n        fila.add("Pedido-003");\n\n        while (!fila.isEmpty()) {\n            System.out.println("Processando: " + fila.poll());\n        }\n        System.out.println("Fila vazia: " + fila.isEmpty());\n    }\n}'
    },
    {
        id: 'code_bsearch', stage: 'Senior', region: 'JP Morgan',
        title: 'Binary Search', concept: 'Busca binária / O(log n)',
        language: 'java', fileName: 'BinarySearch.java',
        description: 'Implemente busca binária iterativa:\n1. Método: static int binarySearch(int[] arr, int target)\n2. Retorna o índice do target ou -1\n3. Use while (low <= high) com mid = low + (high - low) / 2\n4. Teste com arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91}',
        starterCode: 'public class BinarySearch {\n    static int binarySearch(int[] arr, int target) {\n        // Implemente aqui\n        return -1;\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};\n        System.out.println(binarySearch(arr, 23));\n        System.out.println(binarySearch(arr, 99));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+BinarySearch/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar BinarySearch.' };
            if (!/static\s+int\s+binarySearch\s*\(\s*int\s*\[\s*\]\s+\w+\s*,\s*int\s+\w+\s*\)/.test(code))
                return { ok: false, msg: 'Erro de compilação: Assinatura: static int binarySearch(int[] arr, int target)' };
            if (!/while\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use while (low <= high) para o loop de busca.' };
            if (!/mid/.test(code)) return { ok: false, msg: 'Erro semântico: Calcule int mid = (low + high) / 2;' };
            if (!/return\s+-?\s*1/.test(code) && !/return\s+\w+/.test(code)) return { ok: false, msg: 'Erro semântico: Retorne -1 quando não encontrar.' };
            if (!/low/.test(code) || !/high/.test(code)) return { ok: false, msg: 'Erro semântico: Use variaveis low e high para os limites.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 5\n> -1\n\nComplexidade: O(log n) -- 20 comparacoes para 1 milhao de elementos.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Busca binária só funciona em arrays ORDENADOS.\n2. Estratégia: dividir e conquistar. Olhe o meio. Se alvo < meio, descarte metade direita. Se alvo > meio, descarte metade esquerda.\n3. A cada passo, o espaço de busca cai pela METADE. log2(1.000.000) = ~20 passos.\n4. Variáveis: low (início), high (fim), mid (meio).\n\nCOLA -- Copie este código na IDE:\n\npublic class BinarySearch {\n    static int binarySearch(int[] arr, int target) {\n        int low = 0, high = arr.length - 1;\n        while (low <= high) {\n            int mid = low + (high - low) / 2;\n            if (arr[mid] == target) return mid;\n            else if (arr[mid] < target) low = mid + 1;\n            else high = mid - 1;\n        }\n        return -1;\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};\n        System.out.println(binarySearch(arr, 23));\n        System.out.println(binarySearch(arr, 99));\n    }\n}'
    },
    // ── STAFF ───────────────────────────────────────────────────────────────
    {
        id: 'code_twosum', stage: 'Staff', region: 'Tesla',
        title: 'Two Sum (HashMap)', concept: 'Hash lookup O(n) / Otimização',
        language: 'java', fileName: 'TwoSum.java',
        description: 'Implemente Two Sum com HashMap:\n1. Método: static int[] twoSum(int[] nums, int target)\n2. Retorna índices dos dois números que somam target\n3. Use HashMap para lookup O(1)\n4. Complexidade total: O(n)\n5. Teste: nums={2,7,11,15}, target=9 -> [0,1]',
        starterCode: 'import java.util.HashMap;\nimport java.util.Arrays;\n\npublic class TwoSum {\n    static int[] twoSum(int[] nums, int target) {\n        // Implemente aqui\n        return new int[]{};\n    }\n\n    public static void main(String[] args) {\n        int[] result = twoSum(new int[]{2, 7, 11, 15}, 9);\n        System.out.println(Arrays.toString(result));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+TwoSum/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar TwoSum.' };
            if (!/HashMap/.test(code)) return { ok: false, msg: 'Erro semântico: Use HashMap para obter complexidade O(n).' };
            if (!(/\.put\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use map.put() para armazenar valores vistos.' };
            if (!(/\.containsKey\s*\(/.test(code) || /\.get\s*\(/.test(code))) return { ok: false, msg: 'Erro semântico: Use map.containsKey() ou map.get() para verificar o complemento.' };
            if (!/target\s*-/.test(code) && !/\-\s*\w+\[/.test(code)) return { ok: false, msg: 'Erro semântico: O complemento é target - nums[i]. Verifique se já existe no mapa.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [0, 1]\n\nComplexidade: O(n) -- uma única passada com HashMap.\nBrute force seria O(n^2). Você otimizou.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Força bruta: testar todos os pares = O(n^2). Muito lento.\n2. Insight: para cada número X, o "par" dele é (target - X). Se esse par já apareceu, achamos!\n3. HashMap armazena números já vistos. Para cada novo número, olhamos se o complemento já está lá.\n4. Uma única passagem pelo array = O(n).\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.HashMap;\nimport java.util.Arrays;\n\npublic class TwoSum {\n    static int[] twoSum(int[] nums, int target) {\n        HashMap<Integer, Integer> map = new HashMap<>();\n        for (int i = 0; i < nums.length; i++) {\n            int comp = target - nums[i];\n            if (map.containsKey(comp)) {\n                return new int[]{map.get(comp), i};\n            }\n            map.put(nums[i], i);\n        }\n        return new int[]{};\n    }\n\n    public static void main(String[] args) {\n        int[] result = twoSum(new int[]{2, 7, 11, 15}, 9);\n        System.out.println(Arrays.toString(result));\n    }\n}'
    },
    {
        id: 'code_fibonacci', stage: 'Staff', region: 'Itau',
        title: 'Fibonacci Iterativo', concept: 'Recursão vs Iteração / Eficiência',
        language: 'java', fileName: 'Fibonacci.java',
        description: 'Implemente Fibonacci ITERATIVO (não recursivo):\n1. Método: static long fibonacci(int n)\n2. fibonacci(0)=0, fibonacci(1)=1\n3. fibonacci(n) = fibonacci(n-1) + fibonacci(n-2)\n4. Use loop, NÃO recursão (seria O(2^n))\n5. Teste: fibonacci(10) = 55, fibonacci(20) = 6765',
        starterCode: 'public class Fibonacci {\n    static long fibonacci(int n) {\n        // Implemente aqui (iterativo!)\n        return 0;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(fibonacci(10));\n        System.out.println(fibonacci(20));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Fibonacci/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar Fibonacci.' };
            if (!/static\s+long\s+fibonacci/.test(code)) return { ok: false, msg: 'Erro de compilação: Método: static long fibonacci(int n)' };
            if (/fibonacci\s*\(\s*n\s*-\s*1\s*\)/.test(code)) return { ok: false, msg: 'Erro semântico: Não use recursão! Fibonacci recursivo é O(2^n). Use um loop for com variáveis prev e curr.' };
            if (!/for\s*\(/.test(code) && !/while\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use um loop for ou while. A solução deve ser iterativa O(n).' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 55\n> 6765\n\nComplexidade: O(n) iterativo.\nRecursivo seria O(2^n) = fibonacci(50) levaria HORAS.\nIterativo calcula fibonacci(50) em microssegundos.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Fibonacci recursivo: fib(n) chama fib(n-1) e fib(n-2). Cada um chama mais dois. Explosão exponencial O(2^n).\n2. Insight: não precisamos recalcular valores antigos. Basta guardar os dois últimos.\n3. Variáveis: prev = f(n-2), curr = f(n-1). A cada passo: next = prev + curr.\n4. Avance: prev = curr, curr = next. Repita n vezes. O(n) tempo, O(1) espaço.\n\nCOLA -- Copie este código na IDE:\n\npublic class Fibonacci {\n    static long fibonacci(int n) {\n        if (n <= 1) return n;\n        long prev = 0, curr = 1;\n        for (int i = 2; i <= n; i++) {\n            long next = prev + curr;\n            prev = curr;\n            curr = next;\n        }\n        return curr;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(fibonacci(10));\n        System.out.println(fibonacci(20));\n    }\n}'
    },
    {
        id: 'code_sort', stage: 'Staff', region: 'Uber',
        title: 'Bubble Sort', concept: 'Ordenação / Comparação e troca',
        language: 'java', fileName: 'BubbleSort.java',
        description: 'Implemente Bubble Sort:\n1. Método: static void bubbleSort(int[] arr)\n2. Compare elementos adjacentes e troque se fora de ordem\n3. Repita até não haver mais trocas\n4. Imprima o array ordenado\n5. Teste: {64, 34, 25, 12, 22, 11, 90}',
        starterCode: 'import java.util.Arrays;\n\npublic class BubbleSort {\n    static void bubbleSort(int[] arr) {\n        // Implemente aqui\n\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {64, 34, 25, 12, 22, 11, 90};\n        bubbleSort(arr);\n        System.out.println(Arrays.toString(arr));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+BubbleSort/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar BubbleSort.' };
            if (!/static\s+void\s+bubbleSort/.test(code)) return { ok: false, msg: 'Erro de compilação: Método: static void bubbleSort(int[] arr)' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro semântico: Use dois loops for aninhados.' };
            if (!/temp/.test(code) && !/\[\s*\w+\s*\]\s*=/.test(code)) return { ok: false, msg: 'Erro semântico: Para trocar, use uma variável temporária: int temp = arr[j]; arr[j] = arr[j+1]; arr[j+1] = temp;' };
            if (!/\w+\s*>\s*\w+/.test(code) && !/\w+\s*<\s*\w+/.test(code)) return { ok: false, msg: 'Erro semântico: Compare elementos adjacentes: if (arr[j] > arr[j+1])' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [11, 12, 22, 25, 34, 64, 90]\n\nBubble Sort: O(n^2). Simples mas ineficiente para grandes datasets.\nEm produção, use Arrays.sort() que é O(n log n).\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Bubble Sort "borbulha" o maior elemento para o final a cada passagem.\n2. Loop externo: n-1 passagens. Loop interno: compara vizinhos.\n3. Se arr[j] > arr[j+1], troca-os usando variável temporária.\n4. Otimização: se nenhuma troca em uma passagem, array já está ordenado.\n5. Complexidade: O(n^2) -- não use em produção, mas é essencial entender.\n\nCOLA -- Copie este código na IDE:\n\nimport java.util.Arrays;\n\npublic class BubbleSort {\n    static void bubbleSort(int[] arr) {\n        int n = arr.length;\n        for (int i = 0; i < n - 1; i++) {\n            for (int j = 0; j < n - i - 1; j++) {\n                if (arr[j] > arr[j + 1]) {\n                    int temp = arr[j];\n                    arr[j] = arr[j + 1];\n                    arr[j + 1] = temp;\n                }\n            }\n        }\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {64, 34, 25, 12, 22, 11, 90};\n        bubbleSort(arr);\n        System.out.println(Arrays.toString(arr));\n    }\n}'
    },
    // ── PRINCIPAL ───────────────────────────────────────────────────────────
    {
        id: 'code_palindrome', stage: 'Principal', region: 'Santander',
        title: 'Verificar Palíndromo', concept: 'Dois ponteiros / String manipulation',
        language: 'java', fileName: 'Palindrome.java',
        description: 'Implemente verificação de palíndromo:\n1. Método: static boolean isPalindrome(String s)\n2. Ignore maiúsculas/minúsculas e caracteres não-alfanuméricos\n3. Use dois ponteiros (início e fim)\n4. Teste: "A man, a plan, a canal: Panama" -> true\n5. Teste: "race a car" -> false',
        starterCode: 'public class Palindrome {\n    static boolean isPalindrome(String s) {\n        // Implemente aqui\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isPalindrome("A man, a plan, a canal: Panama"));\n        System.out.println(isPalindrome("race a car"));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Palindrome/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar Palindrome.' };
            if (!/static\s+boolean\s+isPalindrome/.test(code)) return { ok: false, msg: 'Erro de compilação: Método: static boolean isPalindrome(String s)' };
            if (!/toLowerCase/.test(code) && !/toUpperCase/.test(code)) return { ok: false, msg: 'Erro semântico: Converta para minúsculas com s.toLowerCase() para ignorar case.' };
            if (!/Character\s*\.\s*isLetterOrDigit/.test(code) && !/replaceAll/.test(code) && !/isAlphanumeric/.test(code))
                return { ok: false, msg: 'Erro semântico: Filtre caracteres não-alfanuméricos com Character.isLetterOrDigit() ou replaceAll("[^a-zA-Z0-9]", "")' };
            if (!/while/.test(code) && !/for/.test(code)) return { ok: false, msg: 'Erro semântico: Use um loop com dois ponteiros (left e right).' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> true\n> false\n\nTécnica: Two Pointers. Complexidade O(n), espaço O(1).\nEssencial em entrevistas de Big Tech.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Palíndromo = lê igual de trás para frente.\n2. Primeiro, limpe a string: remova tudo que não é letra/dígito, converta para minúsculas.\n3. Dois ponteiros: left no início, right no fim.\n4. Compare s[left] com s[right]. Se diferentes, não é palíndromo.\n5. Se left >= right, já comparou tudo. É palíndromo.\n\nCOLA -- Copie este código na IDE:\n\npublic class Palindrome {\n    static boolean isPalindrome(String s) {\n        String clean = s.toLowerCase().replaceAll("[^a-z0-9]", "");\n        int left = 0, right = clean.length() - 1;\n        while (left < right) {\n            if (clean.charAt(left) != clean.charAt(right)) return false;\n            left++;\n            right--;\n        }\n        return true;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isPalindrome("A man, a plan, a canal: Panama"));\n        System.out.println(isPalindrome("race a car"));\n    }\n}'
    },
    {
        id: 'code_reverse', stage: 'Principal', region: 'Bradesco',
        title: 'Reverter Lista In-Place', concept: 'Manipulação de ponteiros / In-place',
        language: 'java', fileName: 'ReverseList.java',
        description: 'Implemente reversão de lista encadeada:\n1. Classe ListNode com int val e ListNode next\n2. Método: static ListNode reverseList(ListNode head)\n3. Reverta in-place (sem criar nova lista)\n4. Use 3 ponteiros: prev, curr, next\n5. Complexidade: O(n) tempo, O(1) espaço',
        starterCode: 'public class ReverseList {\n    static class ListNode {\n        int val;\n        ListNode next;\n        ListNode(int v) { val = v; }\n    }\n\n    static ListNode reverseList(ListNode head) {\n        // Implemente aqui\n        return head;\n    }\n\n    public static void main(String[] args) {\n        ListNode head = new ListNode(1);\n        head.next = new ListNode(2);\n        head.next.next = new ListNode(3);\n        head.next.next.next = new ListNode(4);\n\n        ListNode rev = reverseList(head);\n        while (rev != null) {\n            System.out.print(rev.val + " ");\n            rev = rev.next;\n        }\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+ReverseList/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar ReverseList.' };
            if (!/class\s+ListNode/.test(code)) return { ok: false, msg: 'Erro de compilação: Defina a classe ListNode com val e next.' };
            if (!/static\s+ListNode\s+reverseList/.test(code)) return { ok: false, msg: 'Erro de compilação: Método: static ListNode reverseList(ListNode head)' };
            if (!/prev/.test(code)) return { ok: false, msg: 'Erro semântico: Use um ponteiro prev (inicializado como null) para rastrear o nó anterior.' };
            if (!/while/.test(code)) return { ok: false, msg: 'Erro semântico: Use while (curr != null) para percorrer a lista.' };
            if (!/\.next/.test(code)) return { ok: false, msg: 'Erro semântico: Manipule os ponteiros .next para inverter as conexões.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 4 3 2 1\n\nLista revertida in-place. O(n) tempo, O(1) espaço.\nClássico de entrevistas: não crie nova lista, apenas inverta ponteiros.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Lista encadeada: cada nó aponta para o próximo. Para reverter, cada nó deve apontar para o ANTERIOR.\n2. Três ponteiros: prev (onde vou apontar), curr (nó atual), next (salvar referência antes de perder).\n3. A cada passo: salve next = curr.next, inverta curr.next = prev, avance prev = curr, curr = next.\n4. Quando curr == null, prev é a nova cabeça.\n\nCOLA -- Copie este código na IDE:\n\npublic class ReverseList {\n    static class ListNode {\n        int val;\n        ListNode next;\n        ListNode(int v) { val = v; }\n    }\n\n    static ListNode reverseList(ListNode head) {\n        ListNode prev = null;\n        ListNode curr = head;\n        while (curr != null) {\n            ListNode next = curr.next;\n            curr.next = prev;\n            prev = curr;\n            curr = next;\n        }\n        return prev;\n    }\n\n    public static void main(String[] args) {\n        ListNode head = new ListNode(1);\n        head.next = new ListNode(2);\n        head.next.next = new ListNode(3);\n        head.next.next.next = new ListNode(4);\n\n        ListNode rev = reverseList(head);\n        while (rev != null) {\n            System.out.print(rev.val + " ");\n            rev = rev.next;\n        }\n    }\n}'
    },
    {
        id: 'code_tree', stage: 'Principal', region: 'Cloud Valley',
        title: 'Inverter Árvore Binária', concept: 'Recursão / Árvore binária',
        language: 'java', fileName: 'InvertTree.java',
        description: 'Implemente a inversão de árvore binária:\n1. Classe TreeNode com int val, TreeNode left, right\n2. Método: static TreeNode invertTree(TreeNode root)\n3. Troca left <-> right recursivamente\n4. Retorna a raiz invertida\n5. Complexidade: O(n)',
        starterCode: 'public class InvertTree {\n    static class TreeNode {\n        int val;\n        TreeNode left, right;\n        TreeNode(int v) { val = v; }\n    }\n\n    static TreeNode invertTree(TreeNode root) {\n        // Implemente aqui\n        return root;\n    }\n\n    public static void main(String[] args) {\n        TreeNode root = new TreeNode(4);\n        root.left = new TreeNode(2);\n        root.right = new TreeNode(7);\n        root.left.left = new TreeNode(1);\n        root.left.right = new TreeNode(3);\n\n        TreeNode inv = invertTree(root);\n        System.out.println(inv.left.val);  // 7\n        System.out.println(inv.right.val); // 2\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+InvertTree/.test(code)) return { ok: false, msg: 'Erro de compilação: A classe deve se chamar InvertTree.' };
            if (!/class\s+TreeNode/.test(code)) return { ok: false, msg: 'Erro de compilação: Defina a classe interna TreeNode com val, left, right.' };
            if (!/static\s+TreeNode\s+invertTree/.test(code)) return { ok: false, msg: 'Erro de compilação: Método: static TreeNode invertTree(TreeNode root)' };
            if (!/invertTree\s*\(\s*root\s*\.\s*left\s*\)/.test(code) && !/invertTree\s*\(\s*\w+\s*\.\s*left\s*\)/.test(code) &&
                !/invertTree\s*\(\s*root\s*\.\s*right\s*\)/.test(code) && !/invertTree\s*\(\s*\w+\s*\.\s*right\s*\)/.test(code))
                return { ok: false, msg: 'Erro semântico: Use recursão: invertTree(root.left) e invertTree(root.right).' };
            if (!/null/.test(code)) return { ok: false, msg: 'Erro semântico: Caso base: if (root == null) return null;' };
            const swapPattern = /(temp|TreeNode\s+\w+)\s*=\s*root\.\s*(left|right)/;
            const directSwap = /root\.\s*left\s*=.*root\.\s*right|root\.\s*right\s*=.*root\.\s*left/;
            if (!swapPattern.test(code) && !directSwap.test(code)) return { ok: false, msg: 'Erro semântico: Troque left e right. Use variável temporária ou troca direta.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 7\n> 2\n\nÁrvore invertida com sucesso. Complexidade O(n).\nEsta é uma questão clássica de entrevistas BigTech.\nProcesso finalizado com código de saída 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Árvore binária: cada nó tem 0, 1 ou 2 filhos (left e right).\n2. Inverter = espelhar. O que estava na esquerda vai para a direita e vice-versa.\n3. Recursão: para cada nó, troque left e right. Depois, inverta a subárvore esquerda e a direita.\n4. Caso base: se o nó é null, retorne null (árvore vazia).\n5. Use uma variável temporária para a troca.\n\nCOLA -- Copie este código na IDE:\n\npublic class InvertTree {\n    static class TreeNode {\n        int val;\n        TreeNode left, right;\n        TreeNode(int v) { val = v; }\n    }\n\n    static TreeNode invertTree(TreeNode root) {\n        if (root == null) return null;\n        TreeNode temp = root.left;\n        root.left = invertTree(root.right);\n        root.right = invertTree(temp);\n        return root;\n    }\n\n    public static void main(String[] args) {\n        TreeNode root = new TreeNode(4);\n        root.left = new TreeNode(2);\n        root.right = new TreeNode(7);\n        root.left.left = new TreeNode(1);\n        root.left.right = new TreeNode(3);\n\n        TreeNode inv = invertTree(root);\n        System.out.println(inv.left.val);\n        System.out.println(inv.right.val);\n    }\n}'
    },
    // ── NEW: DISNEY (Junior) - Interface + Polimorfismo ─────────────────────
    {
        id: 'code_polymorphism', stage: 'Junior', region: 'Disney',
        title: 'Interface e Polimorfismo', concept: 'OOP / Interface / Polimorfismo',
        language: 'java', fileName: 'CharacterDemo.java',
        description: 'Implemente polimorfismo com interface:\n1. Interface Personagem com m\u00e9todo String acao()\n2. Classe Heroi implements Personagem: retorna \"Her\u00f3i luta!\"\n3. Classe Vilao implements Personagem: retorna \"Vil\u00e3o ataca!\"\n4. No main, crie array Personagem[] e chame acao() de cada',
        starterCode: '// Crie a interface e as classes aqui\n\npublic class CharacterDemo {\n    public static void main(String[] args) {\n        // Crie o array de Personagem e chame acao()\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/interface\s+Personagem/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: Declare a interface Personagem com o m\u00e9todo acao().' };
            if (!/class\s+Heroi\s+implements\s+Personagem/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe Heroi deve implementar Personagem.' };
            if (!/class\s+Vilao\s+implements\s+Personagem/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe Vilao deve implementar Personagem.' };
            if (!/String\s+acao\s*\(\s*\)/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: O m\u00e9todo deve ser: String acao()' };
            if (!/Personagem\s*\[\s*\]/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Crie um array de Personagem[]. Ex: Personagem[] p = { new Heroi(), new Vilao() };' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um loop for para chamar acao() de cada personagem.' };
            if (!/\.acao\s*\(\s*\)/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Chame o m\u00e9todo acao() de cada personagem.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Her\u00f3i luta!\n> Vil\u00e3o ataca!\n\nPolimorfismo: mesma interface, comportamentos diferentes.\nEsse \u00e9 o pilar da OOP em toda Big Tech.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Interface = contrato. Define O QUE fazer, n\u00e3o COMO.\n2. Cada classe implementa a interface com seu pr\u00f3prio comportamento.\n3. Um array de Personagem pode conter Heroi e Vilao.\n4. Ao chamar acao(), Java executa a vers\u00e3o correta automaticamente.\n5. Sempre use @Override ao implementar m\u00e9todos de interface.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\ninterface Personagem {\n    String acao();\n}\n\nclass Heroi implements Personagem {\n    @Override\n    public String acao() {\n        return \"Her\u00f3i luta!\";\n    }\n}\n\nclass Vilao implements Personagem {\n    @Override\n    public String acao() {\n        return \"Vil\u00e3o ataca!\";\n    }\n}\n\npublic class CharacterDemo {\n    public static void main(String[] args) {\n        Personagem[] p = { new Heroi(), new Vilao() };\n        for (Personagem x : p) {\n            System.out.println(x.acao());\n        }\n    }\n}'
    },
    // ── NEW: IBM (Mid) - Valid Parentheses ──────────────────────────────────
    {
        id: 'code_brackets', stage: 'Mid', region: 'IBM',
        title: 'Validar Par\u00eanteses', concept: 'Stack / Bracket Matching',
        language: 'java', fileName: 'ValidParentheses.java',
        description: 'Verifique se uma string de par\u00eanteses \u00e9 v\u00e1lida:\n1. M\u00e9todo: static boolean isValid(String s)\n2. Cada ( deve fechar com ), [ com ], { com }\n3. Use uma Stack<Character>\n4. Teste: \"({[]})\" \u2192 true, \"([)]\" \u2192 false',
        starterCode: 'import java.util.Stack;\n\npublic class ValidParentheses {\n    static boolean isValid(String s) {\n        // Implemente aqui\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isValid(\"({[]})\")); \n        System.out.println(isValid(\"([)]\")); \n        System.out.println(isValid(\"{[]}\")); \n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+ValidParentheses/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar ValidParentheses.' };
            if (!/static\s+boolean\s+isValid/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static boolean isValid(String s)' };
            if (!/Stack/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use uma Stack para rastrear os par\u00eanteses abertos.' };
            if (!/\.push\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use stack.push() para empilhar caracteres de abertura.' };
            if (!/\.pop\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use stack.pop() para desempilhar e comparar.' };
            if (!/isEmpty/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Verifique se a stack est\u00e1 vazia com isEmpty().' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> true\n> false\n> true\n\nProblema #1 de Stack no LeetCode. Cobrado em toda Big Tech.\nComplexidade: O(n) tempo, O(n) espa\u00e7o.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Para cada caractere de abertura ( [ {, empilhe na Stack.\n2. Para cada fechamento ) ] }, verifique se o topo \u00e9 o par correspondente.\n3. Se n\u00e3o for, a string \u00e9 inv\u00e1lida.\n4. No final, a Stack deve estar vazia.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\nimport java.util.Stack;\n\npublic class ValidParentheses {\n    static boolean isValid(String s) {\n        Stack<Character> stack = new Stack<>();\n        for (char c : s.toCharArray()) {\n            if (c == \'(\' || c == \'[\' || c == \'{\') {\n                stack.push(c);\n            } else {\n                if (stack.isEmpty()) return false;\n                char top = stack.pop();\n                if (c == \')\' && top != \'(\') return false;\n                if (c == \']\' && top != \'[\') return false;\n                if (c == \'}\' && top != \'{\') return false;\n            }\n        }\n        return stack.isEmpty();\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isValid(\"({[]})\"));\n        System.out.println(isValid(\"([)]\"));\n        System.out.println(isValid(\"{[]}\"));\n    }\n}'
    },
    // ── NEW: PAYPAL (Senior) - Anagram Detection ────────────────────────────
    {
        id: 'code_anagram', stage: 'Senior', region: 'PayPal',
        title: 'Detector de Anagrama', concept: 'HashMap / Contagem de caracteres',
        language: 'java', fileName: 'AnagramCheck.java',
        description: 'Verifique se duas strings s\u00e3o anagramas:\n1. M\u00e9todo: static boolean isAnagram(String s, String t)\n2. Anagrama: mesmas letras, ordem diferente\n3. Use um array de contagem int[26]\n4. Teste: \"listen\",\"silent\" \u2192 true\n5. Teste: \"hello\",\"world\" \u2192 false',
        starterCode: 'public class AnagramCheck {\n    static boolean isAnagram(String s, String t) {\n        // Implemente aqui\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isAnagram(\"listen\", \"silent\"));\n        System.out.println(isAnagram(\"hello\", \"world\"));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+AnagramCheck/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar AnagramCheck.' };
            if (!/static\s+boolean\s+isAnagram/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static boolean isAnagram(String s, String t)' };
            if (!/length/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Verifique se as strings t\u00eam o mesmo tamanho primeiro.' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um loop para percorrer os caracteres.' };
            if (!/charAt/.test(code) && !/toCharArray/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use charAt() ou toCharArray() para acessar caracteres.' };
            if (!/int\s*\[\s*26\s*\]/.test(code) && !/int\s*\[\s*\]/.test(code) && !/HashMap/.test(code) && !/sort/.test(code))
                return { ok: false, msg: 'Erro sem\u00e2ntico: Use uma estrutura de contagem: int[26] para frequencia de letras, ou HashMap, ou ordene as strings.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> true\n> false\n\nAnagramas: mesmas letras, frequ\u00eancias iguais.\nUsado em detec\u00e7\u00e3o de fraude e processamento de texto.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Se os tamanhos s\u00e3o diferentes, n\u00e3o \u00e9 anagrama.\n2. Normalize com toLowerCase() para ignorar mai\u00fasculas.\n3. Conte a frequ\u00eancia de cada letra na primeira string.\n4. Subtraia a frequ\u00eancia de cada letra da segunda.\n5. Se todas as contagens s\u00e3o 0, \u00e9 anagrama. Use int[26] para letras (a-z).\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\npublic class AnagramCheck {\n    static boolean isAnagram(String s, String t) {\n        s = s.toLowerCase();\n        t = t.toLowerCase();\n        if (s.length() != t.length()) return false;\n        int[] count = new int[26];\n        for (int i = 0; i < s.length(); i++) {\n            count[s.charAt(i) - \'a\']++;\n            count[t.charAt(i) - \'a\']--;\n        }\n        for (int c : count) {\n            if (c != 0) return false;\n        }\n        return true;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isAnagram(\"listen\", \"silent\"));\n        System.out.println(isAnagram(\"hello\", \"world\"));\n    }\n}'
    },
    // ── NEW: NETFLIX (Senior) - Sliding Window / Kadane ─────────────────────
    {
        id: 'code_kadane', stage: 'Senior', region: 'Netflix',
        title: 'Subarray de Soma M\u00e1xima', concept: 'Programa\u00e7\u00e3o Din\u00e2mica / Kadane O(n)',
        language: 'java', fileName: 'MaxSubarray.java',
        description: 'Encontre o subarray cont\u00edguo de maior soma:\n1. M\u00e9todo: static int maxSubArray(int[] nums)\n2. Use o algoritmo de Kadane\n3. Mantenha soma atual e soma m\u00e1xima\n4. Teste: {-2,1,-3,4,-1,2,1,-5,4} \u2192 6\n   (subarray [4,-1,2,1])',
        starterCode: 'public class MaxSubarray {\n    static int maxSubArray(int[] nums) {\n        // Implemente aqui\n        return 0;\n    }\n\n    public static void main(String[] args) {\n        int[] nums = {-2, 1, -3, 4, -1, 2, 1, -5, 4};\n        System.out.println(maxSubArray(nums));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+MaxSubarray/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar MaxSubarray.' };
            if (!/static\s+int\s+maxSubArray/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static int maxSubArray(int[] nums)' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um loop para percorrer o array.' };
            if (!/Math\.max/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use Math.max() para comparar soma atual vs novo elemento e atualizar o m\u00e1ximo.' };
            if ((code.match(/Math\.max/g) || []).length < 2) return { ok: false, msg: 'Erro sem\u00e2ntico: Kadane precisa de DOIS Math.max(): um para currSum e outro para maxSum.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 6\n\nAlgoritmo de Kadane: O(n) tempo, O(1) espa\u00e7o.\nUsado em an\u00e1lise de s\u00e9ries temporais e streaming.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Kadane: para cada posi\u00e7\u00e3o, decida: continuar o subarray ou come\u00e7ar novo.\n2. Se soma_atual + nums[i] < nums[i], melhor come\u00e7ar do zero.\n3. soma_atual = Math.max(nums[i], soma_atual + nums[i])\n4. soma_maxima = Math.max(soma_maxima, soma_atual)\n5. Uma \u00fanica passagem: O(n).\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\npublic class MaxSubarray {\n    static int maxSubArray(int[] nums) {\n        int maxSum = nums[0];\n        int currSum = nums[0];\n        for (int i = 1; i < nums.length; i++) {\n            currSum = Math.max(nums[i], currSum + nums[i]);\n            maxSum = Math.max(maxSum, currSum);\n        }\n        return maxSum;\n    }\n\n    public static void main(String[] args) {\n        int[] nums = {-2, 1, -3, 4, -1, 2, 1, -5, 4};\n        System.out.println(maxSubArray(nums));\n    }\n}'
    },
    // ── NEW: SPACEX (Staff) - HashSet / Contains Duplicate ──────────────────
    {
        id: 'code_hashset', stage: 'Staff', region: 'SpaceX',
        title: 'Contains Duplicate (HashSet)', concept: 'Set / Deduplica\u00e7\u00e3o O(n)',
        language: 'java', fileName: 'ContainsDuplicate.java',
        description: 'Verifique se um array cont\u00e9m duplicatas:\n1. M\u00e9todo: static boolean containsDuplicate(int[] nums)\n2. Use HashSet para detec\u00e7\u00e3o O(1)\n3. Se o elemento j\u00e1 existe no set, h\u00e1 duplicata\n4. Teste: {1,2,3,1} \u2192 true\n5. Teste: {1,2,3,4} \u2192 false',
        starterCode: 'import java.util.HashSet;\n\npublic class ContainsDuplicate {\n    static boolean containsDuplicate(int[] nums) {\n        // Implemente aqui\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(containsDuplicate(new int[]{1, 2, 3, 1}));\n        System.out.println(containsDuplicate(new int[]{1, 2, 3, 4}));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+ContainsDuplicate/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar ContainsDuplicate.' };
            if (!/static\s+boolean\s+containsDuplicate/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static boolean containsDuplicate(int[] nums)' };
            if (!/HashSet/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use HashSet para verifica\u00e7\u00e3o O(1).' };
            if (!/\.add\s*\(/.test(code) || !/\.contains\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use set.contains() para verificar e set.add() para inserir.' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um loop para percorrer o array.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> true\n> false\n\nHashSet: inser\u00e7\u00e3o e busca O(1). Deduplica\u00e7\u00e3o em uma passagem.\nFundamental para telemetria e processamento de dados.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. For\u00e7a bruta: comparar todos os pares = O(n\u00b2). Muito lento.\n2. HashSet: cada elemento \u00e9 inserido e buscado em O(1).\n3. Para cada n\u00famero: se j\u00e1 est\u00e1 no set, retorne true. Sen\u00e3o, adicione.\n4. Se terminar o loop sem duplicata, retorne false.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\nimport java.util.HashSet;\n\npublic class ContainsDuplicate {\n    static boolean containsDuplicate(int[] nums) {\n        HashSet<Integer> set = new HashSet<>();\n        for (int num : nums) {\n            if (set.contains(num)) return true;\n            set.add(num);\n        }\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(containsDuplicate(new int[]{1, 2, 3, 1}));\n        System.out.println(containsDuplicate(new int[]{1, 2, 3, 4}));\n    }\n}'
    },
    // ── NEW: NVIDIA (Staff) - Merge Sort ────────────────────────────────────
    {
        id: 'code_mergesort', stage: 'Staff', region: 'Nvidia',
        title: 'Merge Sort', concept: 'Ordena\u00e7\u00e3o O(n log n) / Dividir e Conquistar',
        language: 'java', fileName: 'MergeSort.java',
        description: 'Implemente Merge Sort:\n1. M\u00e9todo: static void mergeSort(int[] arr, int left, int right)\n2. Auxiliar: static void merge(int[] arr, int l, int m, int r)\n3. Divida ao meio, ordene cada metade, mescle\n4. Teste: {38, 27, 43, 3, 9, 82, 10}',
        starterCode: 'import java.util.Arrays;\n\npublic class MergeSort {\n    static void mergeSort(int[] arr, int left, int right) {\n        // Implemente aqui\n    }\n\n    static void merge(int[] arr, int l, int m, int r) {\n        // Implemente aqui\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {38, 27, 43, 3, 9, 82, 10};\n        mergeSort(arr, 0, arr.length - 1);\n        System.out.println(Arrays.toString(arr));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+MergeSort/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar MergeSort.' };
            if (!/static\s+void\s+mergeSort/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static void mergeSort(int[] arr, int left, int right)' };
            if (!/static\s+void\s+merge\b/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo auxiliar: static void merge(int[] arr, int l, int m, int r)' };
            if (!/mid/.test(code) && !/meio/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Calcule o ponto m\u00e9dio: int mid = (left + right) / 2;' };
            if (!/mergeSort\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use chamadas recursivas de mergeSort().' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [3, 9, 10, 27, 38, 43, 82]\n\nMerge Sort: O(n log n) garantido. Est\u00e1vel.\nUsado em produ\u00e7\u00e3o quando estabilidade importa.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Dividir: parta o array ao meio recursivamente at\u00e9 ter arrays de 1.\n2. Conquistar: arrays de 1 elemento j\u00e1 est\u00e3o ordenados.\n3. Combinar: mescle dois arrays ordenados comparando elementos.\n4. Complexidade: O(n log n) sempre.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\nimport java.util.Arrays;\n\npublic class MergeSort {\n    static void mergeSort(int[] arr, int left, int right) {\n        if (left < right) {\n            int mid = (left + right) / 2;\n            mergeSort(arr, left, mid);\n            mergeSort(arr, mid + 1, right);\n            merge(arr, left, mid, right);\n        }\n    }\n\n    static void merge(int[] arr, int l, int m, int r) {\n        int n1 = m - l + 1, n2 = r - m;\n        int[] leftArr = new int[n1], rightArr = new int[n2];\n        for (int i = 0; i < n1; i++) leftArr[i] = arr[l + i];\n        for (int j = 0; j < n2; j++) rightArr[j] = arr[m + 1 + j];\n        int i = 0, j = 0, k = l;\n        while (i < n1 && j < n2) {\n            if (leftArr[i] <= rightArr[j]) arr[k++] = leftArr[i++];\n            else arr[k++] = rightArr[j++];\n        }\n        while (i < n1) arr[k++] = leftArr[i++];\n        while (j < n2) arr[k++] = rightArr[j++];\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {38, 27, 43, 3, 9, 82, 10};\n        mergeSort(arr, 0, arr.length - 1);\n        System.out.println(Arrays.toString(arr));\n    }\n}'
    },
    // ── NEW: AURORA LABS (Staff) - Graph BFS ─────────────────────────────────────
    {
        id: 'code_bfs', stage: 'Staff', region: 'Aurora Labs',
        title: 'Travessia BFS em Grafo', concept: 'Grafo / Busca em Largura',
        language: 'java', fileName: 'GraphBFS.java',
        description: 'Implemente BFS (Busca em Largura) num grafo:\n1. Grafo com lista de adjac\u00eancia (HashMap)\n2. M\u00e9todo: static List<Integer> bfs(Map<Integer, List<Integer>> graph, int start)\n3. Use Queue para a fila e Set para visitados\n4. Retorne a ordem de visita\u00e7\u00e3o',
        starterCode: 'import java.util.*;\n\npublic class GraphBFS {\n    static List<Integer> bfs(Map<Integer, List<Integer>> graph, int start) {\n        // Implemente aqui\n        return new ArrayList<>();\n    }\n\n    public static void main(String[] args) {\n        Map<Integer, List<Integer>> graph = new HashMap<>();\n        graph.put(0, Arrays.asList(1, 2));\n        graph.put(1, Arrays.asList(0, 3, 4));\n        graph.put(2, Arrays.asList(0, 4));\n        graph.put(3, Arrays.asList(1));\n        graph.put(4, Arrays.asList(1, 2));\n        System.out.println(bfs(graph, 0));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+GraphBFS/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar GraphBFS.' };
            if (!/static.*bfs\s*\(/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: Declare o m\u00e9todo bfs com os par\u00e2metros corretos.' };
            if (!/Queue/.test(code) && !/LinkedList/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use uma Queue (fila) para a travessia BFS.' };
            if (!/Set/.test(code) && !/visited/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um Set para rastrear n\u00f3s j\u00e1 visitados.' };
            if (!/\.poll\s*\(/.test(code) && !/\.remove\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use queue.poll() para desenfileirar o pr\u00f3ximo n\u00f3.' };
            if (!/while/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use while (!queue.isEmpty()) para processar todos os n\u00f3s.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [0, 1, 2, 3, 4]\n\nBFS: visita todos os n\u00f3s por camada (n\u00edvel).\nBase de sistemas conectados, redes sociais e shortest path.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. BFS = visitar n\u00f3s por camada. Primeiro os vizinhos, depois os vizinhos dos vizinhos.\n2. Estrutura: Queue (fila FIFO) + Set (visitados).\n3. Comece pelo n\u00f3 inicial: adicione \u00e0 fila e ao set.\n4. Enquanto a fila n\u00e3o estiver vazia: retire um n\u00f3, processe, adicione vizinhos.\n5. Complexidade: O(V + E) onde V=v\u00e9rtices, E=arestas.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\nimport java.util.*;\n\npublic class GraphBFS {\n    static List<Integer> bfs(Map<Integer, List<Integer>> graph, int start) {\n        List<Integer> result = new ArrayList<>();\n        Queue<Integer> queue = new LinkedList<>();\n        Set<Integer> visited = new HashSet<>();\n        queue.add(start);\n        visited.add(start);\n        while (!queue.isEmpty()) {\n            int node = queue.poll();\n            result.add(node);\n            for (int neighbor : graph.getOrDefault(node, List.of())) {\n                if (!visited.contains(neighbor)) {\n                    visited.add(neighbor);\n                    queue.add(neighbor);\n                }\n            }\n        }\n        return result;\n    }\n\n    public static void main(String[] args) {\n        Map<Integer, List<Integer>> graph = new HashMap<>();\n        graph.put(0, Arrays.asList(1, 2));\n        graph.put(1, Arrays.asList(0, 3, 4));\n        graph.put(2, Arrays.asList(0, 4));\n        graph.put(3, Arrays.asList(1));\n        graph.put(4, Arrays.asList(1, 2));\n        System.out.println(bfs(graph, 0));\n    }\n}'
    },
    // ── NEW: GEMINI (Principal) - Priority Queue / Heap ─────────────────────
    {
        id: 'code_heap', stage: 'Principal', region: 'Gemini',
        title: 'Fila de Prioridade (Heap)', concept: 'PriorityQueue / Min-Heap',
        language: 'java', fileName: 'TaskScheduler.java',
        description: 'Processe tarefas por prioridade usando PriorityQueue:\n1. Classe Task com String nome e int prioridade\n2. Implemente Comparable<Task>\n3. Adicione tarefas com prioridades diferentes\n4. Processe (poll) e imprima em ordem de prioridade',
        starterCode: 'import java.util.PriorityQueue;\n\npublic class TaskScheduler {\n    static class Task implements Comparable<Task> {\n        String nome;\n        int prioridade;\n        Task(String n, int p) { nome = n; prioridade = p; }\n\n        public int compareTo(Task other) {\n            // Implemente aqui\n            return 0;\n        }\n    }\n\n    public static void main(String[] args) {\n        PriorityQueue<Task> pq = new PriorityQueue<>();\n        // Adicione tarefas e processe\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+TaskScheduler/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar TaskScheduler.' };
            if (!/class\s+Task/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: Defina a classe interna Task.' };
            if (!/implements\s+Comparable/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: Task deve implementar Comparable<Task>.' };
            if (!/compareTo/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: Implemente o m\u00e9todo compareTo().' };
            if (!/PriorityQueue/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use PriorityQueue para processar por prioridade.' };
            if (!/\.add\s*\(/.test(code) || !/\.poll\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use pq.add() para inserir e pq.poll() para extrair.' };
            if (!/prioridade/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Compare this.prioridade com other.prioridade no compareTo.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [1] Deploy em produ\u00e7\u00e3o\n> [2] Code review\n> [5] Atualizar docs\n\nPriorityQueue: Min-Heap. Inser\u00e7\u00e3o e extra\u00e7\u00e3o O(log n).\nUsado em A*, Dijkstra, agendamento de tarefas.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. PriorityQueue = Min-Heap. O menor elemento sempre sai primeiro.\n2. Implemente Comparable e o m\u00e9todo compareTo() com @Override.\n3. compareTo retorna negativo se this < other, 0 se igual, positivo se >.\n4. Use Integer.compare() -- NUNCA subtra\u00e7\u00e3o direta (causa overflow com valores extremos).\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\nimport java.util.PriorityQueue;\n\npublic class TaskScheduler {\n    static class Task implements Comparable<Task> {\n        String nome;\n        int prioridade;\n        Task(String n, int p) { nome = n; prioridade = p; }\n\n        @Override\n        public int compareTo(Task other) {\n            return Integer.compare(this.prioridade, other.prioridade);\n        }\n    }\n\n    public static void main(String[] args) {\n        PriorityQueue<Task> pq = new PriorityQueue<>();\n        pq.add(new Task(\"Atualizar docs\", 5));\n        pq.add(new Task(\"Deploy em produ\u00e7\u00e3o\", 1));\n        pq.add(new Task(\"Code review\", 2));\n\n        while (!pq.isEmpty()) {\n            Task t = pq.poll();\n            System.out.println(\"[\" + t.prioridade + \"] \" + t.nome);\n        }\n    }\n}'
    },
    // ── NEW: NEXUS LABS (Principal) - Climbing Stairs / DP ──────────────────────
    {
        id: 'code_dp', stage: 'Principal', region: 'Nexus Labs',
        title: 'Climbing Stairs (DP)', concept: 'Programa\u00e7\u00e3o Din\u00e2mica / Subproblemas',
        language: 'java', fileName: 'ClimbingStairs.java',
        description: 'Conte quantas formas de subir n degraus:\n1. M\u00e9todo: static int climbStairs(int n)\n2. Pode subir 1 ou 2 degraus por vez\n3. Use Programa\u00e7\u00e3o Din\u00e2mica (N\u00c3O recurs\u00e3o pura)\n4. Teste: n=2 \u2192 2, n=5 \u2192 8, n=10 \u2192 89',
        starterCode: 'public class ClimbingStairs {\n    static int climbStairs(int n) {\n        // Implemente aqui com DP\n        return 0;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(climbStairs(2));\n        System.out.println(climbStairs(5));\n        System.out.println(climbStairs(10));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+ClimbingStairs/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: A classe deve se chamar ClimbingStairs.' };
            if (!/static\s+int\s+climbStairs/.test(code)) return { ok: false, msg: 'Erro de compila\u00e7\u00e3o: M\u00e9todo: static int climbStairs(int n)' };
            if (/climbStairs\s*\(\s*n\s*-\s*1\s*\)\s*\+\s*climbStairs\s*\(\s*n\s*-\s*2\s*\)/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Recurs\u00e3o pura \u00e9 O(2^n). Use DP com loop iterativo.' };
            if (!/for\s*\(/.test(code) && !/while\s*\(/.test(code)) return { ok: false, msg: 'Erro sem\u00e2ntico: Use um loop iterativo para construir a solu\u00e7\u00e3o de baixo para cima.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 2\n> 8\n> 89\n\nPrograma\u00e7\u00e3o Din\u00e2mica: resolver subproblemas menores primeiro.\nclimbStairs(n) = climbStairs(n-1) + climbStairs(n-2)\nIterativo: O(n) tempo, O(1) espa\u00e7o.\nProcesso finalizado com c\u00f3digo de sa\u00edda 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Para chegar ao degrau n, voc\u00ea veio do n-1 (1 passo) ou n-2 (2 passos).\n2. Formas(n) = Formas(n-1) + Formas(n-2). \u00c9 Fibonacci!\n3. Recurs\u00e3o pura: O(2^n). DP iterativo: O(n).\n4. Guarde os dois \u00faltimos valores e avance.\n\nCOLA -- Copie este c\u00f3digo na IDE:\n\npublic class ClimbingStairs {\n    static int climbStairs(int n) {\n        if (n <= 2) return n;\n        int prev = 1, curr = 2;\n        for (int i = 3; i <= n; i++) {\n            int next = prev + curr;\n            prev = curr;\n            curr = next;\n        }\n        return curr;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(climbStairs(2));\n        System.out.println(climbStairs(5));\n        System.out.println(climbStairs(10));\n    }\n}'
    },
];

// ---- challenge scale tracks (Apple/Nubank) ----
const SCALE_MISSIONS = {
    code_var: {
        requiredValidations: 3,
        mentor: 'STEVE JOBS',
        steps: [
            {
                name: 'Base funcional',
                objective: 'Monte a versao base com tipos primitivos e 4 prints.',
            },
            {
                name: 'Modularizacao',
                objective: 'Expanda para um metodo static void printProfile(...) e chame esse metodo no main.',
                validator(code) {
                    if (!/static\s+void\s+printProfile\s*\(/.test(code)) {
                        return { ok: false, msg: 'Apple 2/3: crie o metodo static void printProfile(...).' };
                    }
                    const occurrences = (code.match(/printProfile\s*\(/g) || []).length;
                    if (occurrences < 2) {
                        return { ok: false, msg: 'Apple 2/3: alem de declarar printProfile, faca a chamada dentro do main.' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (APPLE 2/3):\n1. Saia do codigo monolitico no main.\n2. Extraia um metodo para encapsular a impressao.\n3. Chame esse metodo com os dados tipados.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class Variables {\n    static void printProfile(int idade, double salario, String nome, boolean ativo) {\n        System.out.println(idade);\n        System.out.println(salario);\n        System.out.println(nome);\n        System.out.println(ativo);\n    }\n\n    public static void main(String[] args) {\n        int idade = 20;\n        double salario = 3500.50;\n        String nome = "Dev";\n        boolean ativo = true;\n\n        printProfile(idade, salario, nome, ativo);\n    }\n}'
            },
            {
                name: 'Seguranca e padrao',
                objective: 'Expanda para padrao seguro: use constantes final e validacao de idade antes de imprimir.',
                validator(code) {
                    if (!/final\s+int\s+\w+\s*=/.test(code)) {
                        return { ok: false, msg: 'Apple 3/3: adicione pelo menos uma constante final para padrao seguro.' };
                    }
                    if (!/if\s*\(\s*\w+\s*<\s*0\s*\)/.test(code)) {
                        return { ok: false, msg: 'Apple 3/3: valide idade negativa com if (idade < 0).' };
                    }
                    if (!/(throw\s+new\s+IllegalArgumentException|return;)/.test(code)) {
                        return { ok: false, msg: 'Apple 3/3: trate o caso invalido com throw ou return defensivo.' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (APPLE 3/3):\n1. Defina constantes final para contratos de negocio.\n2. Valide idade/salario antes da saida.\n3. Falhe de forma segura quando dado invalido.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class Variables {\n    static final int IDADE_MINIMA = 0;\n    static final double SALARIO_MINIMO = 0.0;\n\n    static void printProfile(int idade, double salario, String nome, boolean ativo) {\n        if (idade < IDADE_MINIMA) {\n            throw new IllegalArgumentException("idade invalida");\n        }\n        if (salario < SALARIO_MINIMO) {\n            throw new IllegalArgumentException("salario invalido");\n        }\n\n        System.out.println(idade);\n        System.out.println(salario);\n        System.out.println(nome);\n        System.out.println(ativo);\n    }\n\n    public static void main(String[] args) {\n        int idade = 20;\n        double salario = 3500.50;\n        String nome = "Dev";\n        boolean ativo = true;\n\n        printProfile(idade, salario, nome, ativo);\n    }\n}'
            },
        ],
    },
    code_fizzbuzz: {
        requiredValidations: 5,
        mentor: 'DAVID VELEZ',
        steps: [
            {
                name: 'Base funcional',
                objective: 'Monte o FizzBuzz base funcionando para 1..15.',
            },
            {
                name: 'Parametrizacao',
                objective: 'Expanda com variavel limite e use esse limite no for.',
                validator(code) {
                    if (!/int\s+limite\s*=/.test(code)) {
                        return { ok: false, msg: 'Nubank 2/5: declare int limite = ... para parametrizar o range.' };
                    }
                    if (!/for\s*\([^;]*;[^;]*<=\s*limite\s*;/.test(code)) {
                        return { ok: false, msg: 'Nubank 2/5: use a variavel limite na condicao do for.' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (NUBANK 2/5):\n1. Tire numero magico do for.\n2. Use limite como parametro de escala.\n3. Mantenha regra de negocio intacta.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class FizzBuzz {\n    public static void main(String[] args) {\n        int limite = 15;\n        for (int i = 1; i <= limite; i++) {\n            if (i % 3 == 0 && i % 5 == 0) {\n                System.out.println("FizzBuzz");\n            } else if (i % 3 == 0) {\n                System.out.println("Fizz");\n            } else if (i % 5 == 0) {\n                System.out.println("Buzz");\n            } else {\n                System.out.println(i);\n            }\n        }\n    }\n}'
            },
            {
                name: 'Metodo de dominio',
                objective: 'Expanda para static String classify(int n) e chame no loop.',
                validator(code) {
                    if (!/static\s+String\s+classify\s*\(\s*int\s+\w+\s*\)/.test(code)) {
                        return { ok: false, msg: 'Nubank 3/5: extraia a regra para static String classify(int n).' };
                    }
                    const directPrint = /System\s*\.\s*out\s*\.\s*println\s*\(\s*classify\s*\(\s*\w+\s*\)\s*\)/.test(code);
                    const viaEmit = /emit\s*\(\s*classify\s*\(\s*\w+\s*\)\s*\)/.test(code);
                    if (!directPrint && !viaEmit) {
                        return { ok: false, msg: 'Nubank 3/5: use classify(i) dentro do loop (println(classify(i)) ou emit(classify(i))).' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (NUBANK 3/5):\n1. Separe regra de negocio da camada de exibicao.\n2. classify(int n) decide Fizz/Buzz/FizzBuzz.\n3. main apenas orquestra o fluxo.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class FizzBuzz {\n    static String classify(int n) {\n        if (n % 3 == 0 && n % 5 == 0) return "FizzBuzz";\n        if (n % 3 == 0) return "Fizz";\n        if (n % 5 == 0) return "Buzz";\n        return String.valueOf(n);\n    }\n\n    public static void main(String[] args) {\n        int limite = 15;\n        for (int i = 1; i <= limite; i++) {\n            System.out.println(classify(i));\n        }\n    }\n}'
            },
            {
                name: 'Camada de saida',
                objective: 'Expanda para static void emit(String out) e passe a imprimir via emit(...).',
                validator(code) {
                    if (!/static\s+void\s+emit\s*\(\s*String\s+\w+\s*\)/.test(code)) {
                        return { ok: false, msg: 'Nubank 4/5: crie static void emit(String out) para centralizar output.' };
                    }
                    if (!/emit\s*\(\s*classify\s*\(\s*\w+\s*\)\s*\)/.test(code) && !/emit\s*\(\s*\w+\s*\)/.test(code)) {
                        return { ok: false, msg: 'Nubank 4/5: use emit(...) no loop para publicar a saida.' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (NUBANK 4/5):\n1. Centralize output para reduzir duplicacao.\n2. main chama emit(...) e nao println direto.\n3. Fica pronto para trocar console por log/telemetria depois.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class FizzBuzz {\n    static String classify(int n) {\n        if (n % 3 == 0 && n % 5 == 0) return "FizzBuzz";\n        if (n % 3 == 0) return "Fizz";\n        if (n % 5 == 0) return "Buzz";\n        return String.valueOf(n);\n    }\n\n    static void emit(String out) {\n        System.out.println(out);\n    }\n\n    public static void main(String[] args) {\n        int limite = 15;\n        for (int i = 1; i <= limite; i++) {\n            emit(classify(i));\n        }\n    }\n}'
            },
            {
                name: 'Observabilidade',
                objective: 'Expanda com contadores e resumo final de execucao.',
                validator(code) {
                    if (!/int\s+countFizz\b/.test(code) || !/int\s+countBuzz\b/.test(code) || !/int\s+countFizzBuzz\b/.test(code)) {
                        return { ok: false, msg: 'Nubank 5/5: declare countFizz, countBuzz e countFizzBuzz.' };
                    }
                    if (!/countFizz\s*\+\+/.test(code) || !/countBuzz\s*\+\+/.test(code) || !/countFizzBuzz\s*\+\+/.test(code)) {
                        return { ok: false, msg: 'Nubank 5/5: incremente os contadores durante o loop.' };
                    }
                    if (!/System\s*\.\s*out\s*\.\s*println\s*\(\s*"Resumo/.test(code)) {
                        return { ok: false, msg: 'Nubank 5/5: imprima um resumo final com os contadores.' };
                    }
                    return { ok: true };
                },
                helpText: 'COMO EXPANDIR (NUBANK 5/5):\n1. Adicione observabilidade para operacao segura.\n2. Conte cada tipo de evento durante o loop.\n3. Publique resumo final para auditoria.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class FizzBuzz {\n    static String classify(int n) {\n        if (n % 3 == 0 && n % 5 == 0) return "FizzBuzz";\n        if (n % 3 == 0) return "Fizz";\n        if (n % 5 == 0) return "Buzz";\n        return String.valueOf(n);\n    }\n\n    static void emit(String out) {\n        System.out.println(out);\n    }\n\n    public static void main(String[] args) {\n        int limite = 15;\n        int countFizz = 0, countBuzz = 0, countFizzBuzz = 0, countNumero = 0;\n\n        for (int i = 1; i <= limite; i++) {\n            String out = classify(i);\n            if ("FizzBuzz".equals(out)) countFizzBuzz++;\n            else if ("Fizz".equals(out)) countFizz++;\n            else if ("Buzz".equals(out)) countBuzz++;\n            else countNumero++;\n\n            emit(out);\n        }\n\n        System.out.println("Resumo -> FizzBuzz: " + countFizzBuzz\n            + ", Fizz: " + countFizz\n            + ", Buzz: " + countBuzz\n            + ", Numero: " + countNumero);\n    }\n}'
            },
        ],
    },
};

/**
 * Maps stage name to index for challenge progression.
 */
const STAGE_ORDER = ['Intern', 'Junior', 'Mid', 'Senior', 'Staff', 'Principal', 'Distinguished'];

// ---- IDE controller ----
const IDE = {
    _currentChallenge: null,
    _currentNpc: null,
    _attempts: 0,
    _maxAttempts: 5,
    _solved: false,
    _scalePlan: null,
    _scalePasses: 0,
    _scaleLastCode: '',
    _baseChallengeDesc: '',

    _selectChallenge(stage, region) {
        // Find a challenge matching the NPC's region (1 unique challenge per company)
        let challenge = region ? CODE_CHALLENGES.find(c => c.region === region) : null;
        if (!challenge) {
            // Fallback: find by stage (or nearest lower)
            challenge = CODE_CHALLENGES.find(c => c.stage === stage);
            if (!challenge) {
                const si = STAGE_ORDER.indexOf(stage);
                for (let i = si; i >= 0; i--) {
                    challenge = CODE_CHALLENGES.find(c => c.stage === STAGE_ORDER[i]);
                    if (challenge) break;
                }
            }
        }
        if (!challenge) challenge = CODE_CHALLENGES[0];
        return challenge;
    },

    _isScalingActive() {
        return !!(this._scalePlan && this._scalePlan.requiredValidations > 1);
    },

    _getScaleStep() {
        if (!this._isScalingActive()) return null;
        const idx = Math.min(this._scalePasses, this._scalePlan.steps.length - 1);
        return this._scalePlan.steps[idx] || null;
    },

    _getScaleProgressLabel() {
        if (!this._isScalingActive()) return '';
        return (this._scalePasses + 1) + '/' + this._scalePlan.requiredValidations;
    },

    _refreshScaleUI() {
        if (!this._currentChallenge) return;
        const descEl = document.getElementById('ideChallengeDesc');
        const conceptEl = document.getElementById('ideConceptTag');

        if (!this._isScalingActive()) {
            if (descEl) descEl.textContent = this._baseChallengeDesc || this._currentChallenge.description || '---';
            if (conceptEl) conceptEl.textContent = this._currentChallenge.concept || '---';
            return;
        }

        const step = this._getScaleStep();
        const progress = this._getScaleProgressLabel();
        const objective = step && step.objective ? step.objective : 'Evolua o codigo para a proxima fase.';
        if (descEl) {
            descEl.textContent = (this._baseChallengeDesc || this._currentChallenge.description || '') +
                '\n\nESCALABILIDADE ' + progress + ': ' + objective;
        }
        if (conceptEl) {
            conceptEl.textContent = (this._currentChallenge.concept || '---') + ' | ESCALA ' + progress;
        }
    },

    _getCurrentHelpText() {
        const ch = this._currentChallenge;
        if (!ch) return '---';
        if (this._isScalingActive()) {
            const step = this._getScaleStep();
            if (step && step.helpText) return step.helpText;
        }
        return ch.helpText || '---';
    },

    _getCurrentHelpMentor() {
        const ch = this._currentChallenge;
        if (this._isScalingActive() && this._scalePlan && this._scalePlan.mentor) {
            return this._scalePlan.mentor;
        }
        if (ch && ch.helpMentor) return ch.helpMentor;
        if (this._currentNpc && this._currentNpc.name) return this._currentNpc.name;
        return 'MENTOR';
    },

    _attemptCoachMessage(challenge, attempts) {
        const title = (challenge && challenge.title) ? challenge.title : 'este desafio';
        if (attempts <= 1) {
            return 'Inteligência Artificial: revise assinatura da classe/metodo em "' + title + '" antes de ajustar algoritmo.';
        }
        if (attempts === 2) {
            return 'Inteligência Artificial: faca dry-run com um exemplo pequeno e confirme cada variavel a cada passo.';
        }
        if (attempts === 3) {
            return 'Inteligência Artificial: quebre o problema em 3 blocos -> entrada, processamento e saida.';
        }
        if (attempts === 4) {
            return 'Inteligência Artificial: valide caso de borda (vazio, unico elemento, limite superior).';
        }
        return 'Inteligência Artificial: compare sua versao com o objetivo do enunciado e simplifique o fluxo principal.';
    },

    /**
     * Opens the IDE overlay with a coding challenge appropriate for the player stage.
     * Called after the theory challenge is answered correctly.
     */
    open(npc, opts = {}) {
        const stage = State.player ? State.player.stage : 'Intern';
        const region = npc ? npc.region : null;
        const selected = opts.preselectedChallenge || this._selectChallenge(stage, region);
        const challenge = selected || CODE_CHALLENGES[0];

        if (!opts.skipPrep) {
            const prepRegion = region || challenge.region || '';
            const opened = Learning.showLiveCodingPrepIfNeeded(prepRegion, challenge, () => {
                IDE.open(npc, { skipPrep: true, preselectedChallenge: challenge });
            });
            if (opened) return;
        }

        this._currentChallenge = challenge;
        this._currentNpc = npc || null;
        this._attempts = 0;
        this._solved = false;
        this._scalePlan = SCALE_MISSIONS[challenge.id] || null;
        this._scalePasses = 0;
        this._scaleLastCode = '';
        this._baseChallengeDesc = challenge.description || '';

        // Populate UI
        document.getElementById('ideFileName').textContent = challenge.fileName;
        const IDE_STAGE_PT = { 'Intern': 'ESTAGIARIO', 'Junior': 'JUNIOR', 'Mid': 'PLENO', 'Senior': 'SENIOR', 'Staff': 'STAFF', 'Principal': 'PRINCIPAL', 'Distinguished': 'CEO' };
        document.getElementById('ideStage').textContent = IDE_STAGE_PT[stage] || stage.toUpperCase();
        document.getElementById('ideSideFileName').textContent = challenge.fileName;
        document.getElementById('ideChallengeTitle').textContent = challenge.title;
        this._refreshScaleUI();
        document.getElementById('ideCodeInput').value = challenge.starterCode || '';
        document.getElementById('ideCodeInput').placeholder = '// Escreva seu código ' + challenge.language.toUpperCase() + ' aqui...';
        document.getElementById('ideSkipBtn').style.display = 'none';

        // Reset CONTINUAR button and restore original buttons
        const continueBtn = document.getElementById('ideContinueBtn');
        if (continueBtn) continueBtn.style.display = 'none';
        document.getElementById('ideRunBtn').style.display = 'flex';
        document.getElementById('ideHelpBtn').style.display = 'flex';

        // Terminal reset
        document.getElementById('ideTermOutput').innerHTML = '<span class="ide-prompt">&gt;</span> Aguardando código...\n<span class="ide-term-info">Desafio: ' + challenge.title + '</span>\n<span class="ide-term-info">Conceito: ' + challenge.concept + '</span>';
        const termStatus = document.getElementById('ideTermStatus');
        if (this._isScalingActive()) {
            const step = this._getScaleStep();
            const term = document.getElementById('ideTermOutput');
            term.innerHTML += '\n<span class="ide-term-info">Escalonamento ativo: ' + this._scalePlan.requiredValidations + ' validacoes obrigatorias nesta empresa.</span>';
            term.innerHTML += '\n<span class="ide-term-info">Fase ' + this._getScaleProgressLabel() + ': ' + (step ? step.objective : 'Evolua o codigo.') + '</span>';
            termStatus.textContent = 'Escala ' + this._getScaleProgressLabel();
        } else {
            termStatus.textContent = 'Pronto';
        }
        termStatus.className = 'ide-terminal-status';

        // Line numbers sync
        this._syncLineNumbers();
        document.getElementById('ideCodeInput').addEventListener('input', () => IDE._syncLineNumbers());

        // Draw characters on canvases
        this._drawPlayerChar();
        this._drawMentorChar();

        // Player name
        document.getElementById('idePlayerName').textContent = State.player ? State.player.name : 'JOGADOR';
        document.getElementById('ideMentorName').textContent = npc ? npc.name : 'MENTOR';

        // Pause music during coding challenge (seamless resume on close)
        SFX.pauseMusic();

        // Show overlay
        document.getElementById('ideOverlay').classList.add('visible');
        StudyChat.open(false);
        document.getElementById('ideCodeInput').focus();

        // On mobile: handle virtual keyboard resizing
        this._setupMobileKeyboardHandlers();
    },

    _setupMobileKeyboardHandlers() {
        const isMobile = window.matchMedia('(max-width: 768px), (pointer: coarse)').matches;
        if (!isMobile) return;

        const codeInput = document.getElementById('ideCodeInput');
        const container = document.querySelector('.ide-container');
        const bottomBar = document.querySelector('.ide-bottombar');

        // When textarea gains focus on mobile, hide bottom bar and expand editor
        codeInput.addEventListener('focus', () => {
            if (bottomBar) bottomBar.style.display = 'none';
            if (container) container.classList.add('keyboard-open');
        });

        codeInput.addEventListener('blur', () => {
            if (bottomBar) bottomBar.style.display = 'flex';
            if (container) container.classList.remove('keyboard-open');
        });

        // Use visualViewport API to detect keyboard open/close
        if (window.visualViewport) {
            const onResize = () => {
                const overlay = document.getElementById('ideOverlay');
                if (!overlay || !overlay.classList.contains('visible')) return;
                const keyboardOpen = window.visualViewport.height < window.innerHeight * 0.75;
                if (keyboardOpen) {
                    if (bottomBar) bottomBar.style.display = 'none';
                    if (container) container.classList.add('keyboard-open');
                } else {
                    if (bottomBar) bottomBar.style.display = 'flex';
                    if (container) container.classList.remove('keyboard-open');
                }
            };
            window.visualViewport.addEventListener('resize', onResize);
        }
    },

    _syncLineNumbers() {
        const textarea = document.getElementById('ideCodeInput');
        const lineNums = document.getElementById('ideLineNumbers');
        const lines = (textarea.value || '').split('\n').length;
        const count = Math.max(lines, 10);
        let html = '';
        for (let i = 1; i <= count; i++) html += '<span>' + i + '</span>';
        lineNums.innerHTML = html;
    },

    runCode() {
        if (this._solved) return;
        const ch = this._currentChallenge;
        if (!ch) return;

        this._attempts++;
        const code = document.getElementById('ideCodeInput').value.trim();
        const term = document.getElementById('ideTermOutput');
        const termStatus = document.getElementById('ideTermStatus');

        if (!code) {
            term.innerHTML += '\n<span class="ide-term-error">ERRO: Editor vazio. Escreva seu código.</span>';
            return;
        }

        // Compile check
        term.innerHTML += '\n<span class="ide-prompt">&gt;</span> javac ' + ch.fileName + '\n';

        let result = ch.validator(code);
        if (result.ok && this._isScalingActive()) {
            const progress = this._getScaleProgressLabel();
            if (this._scalePasses > 0 && code === this._scaleLastCode) {
                result = {
                    ok: false,
                    msg: 'Escala ' + progress + ': expanda o codigo antes de validar novamente. Nao repita exatamente a mesma versao.',
                };
            } else {
                const step = this._getScaleStep();
                if (step && typeof step.validator === 'function') {
                    const stepResult = step.validator(code);
                    if (!stepResult.ok) result = stepResult;
                }
            }
        }

        if (result.ok) {
            term.innerHTML += '<span class="ide-term-success">Compilation successful.</span>\n';
            term.innerHTML += '<span class="ide-prompt">&gt;</span> java ' + ch.fileName.replace('.java', '') + '\n';
            term.innerHTML += '<span class="ide-term-success">' + result.msg + '</span>';
            if (this._isScalingActive()) {
                this._scalePasses += 1;
                this._scaleLastCode = code;
                const required = this._scalePlan.requiredValidations;
                const finishedScaling = this._scalePasses >= required;

                if (!finishedScaling) {
                    const nextStep = this._getScaleStep();
                    term.innerHTML += '\n\n<span class="ide-term-success">FASE VALIDADA (' + this._scalePasses + '/' + required + ').</span>';
                    term.innerHTML += '\n<span class="ide-term-info">Proxima expansao: ' + (nextStep ? nextStep.objective : 'Evolua o codigo.') + '</span>';
                    term.innerHTML += '\n<span class="ide-term-info">Use VER SOLUCAO para a cola da proxima fase.</span>';
                    termStatus.textContent = 'Escala ' + this._getScaleProgressLabel();
                    termStatus.className = 'ide-terminal-status';
                    this._refreshScaleUI();
                    SFX.correct();
                    term.scrollTop = term.scrollHeight;
                    return;
                }

                term.innerHTML += '\n\n<span class="ide-term-success">ESCALABILIDADE CONCLUIDA (' + required + '/' + required + ').</span>';
            }
            term.innerHTML += '\n\n<span class="ide-term-success">DESAFIO COMPLETO! Código validado com sucesso.</span>';
            termStatus.textContent = 'Compilacao OK';
            termStatus.className = 'ide-terminal-status';
            this._solved = true;
            SFX.correct();

            // Show CONTINUAR button instead of auto-closing
            document.getElementById('ideSkipBtn').style.display = 'none';
            const actions = document.querySelector('.ide-actions');
            let continueBtn = document.getElementById('ideContinueBtn');
            if (!continueBtn) {
                continueBtn = document.createElement('button');
                continueBtn.id = 'ideContinueBtn';
                continueBtn.className = 'ide-btn ide-btn-run';
                continueBtn.innerHTML = '<span class="ide-btn-icon">&#10003;</span> CONTINUAR';
                continueBtn.onclick = () => IDE.close();
                actions.appendChild(continueBtn);
            }
            continueBtn.style.display = 'flex';
            // Disable RUN and HELP buttons
            document.getElementById('ideRunBtn').style.display = 'none';
            document.getElementById('ideHelpBtn').style.display = 'none';
        } else {
            term.innerHTML += '<span class="ide-term-error">' + ch.fileName + ': ' + result.msg + '</span>';
            term.innerHTML += '\n<span class="ide-term-error">1 error</span>';
            termStatus.textContent = 'Erro na Compilacao';
            termStatus.className = 'ide-terminal-status error';
            SFX.wrong();
            term.innerHTML += '\n<span class="ide-term-info">' + this._attemptCoachMessage(ch, this._attempts) + '</span>';

            // After 3 failed attempts, show skip button
            if (this._attempts >= 3) {
                document.getElementById('ideSkipBtn').style.display = 'flex';
            }
        }

        // Scroll terminal to bottom
        term.scrollTop = term.scrollHeight;
    },

    askHelp() {
        const ch = this._currentChallenge;
        if (!ch) return;

        document.getElementById('ideHelpMentor').textContent = this._getCurrentHelpMentor();
        document.getElementById('ideHelpContent').textContent = this._getCurrentHelpText();
        document.getElementById('ideHelpOverlay').style.display = 'flex';
    },

    closeHelp() {
        document.getElementById('ideHelpOverlay').style.display = 'none';
        document.getElementById('ideCodeInput').focus();
    },

    skip() {
        const term = document.getElementById('ideTermOutput');
        term.innerHTML += '\n<span class="ide-term-warn">Desafio pulado. Estude o conceito para a próxima vez.</span>';

        // Show the correct answer in terminal as learning opportunity
        const helpText = this._getCurrentHelpText();
        if (this._currentChallenge && helpText) {
            term.innerHTML += '\n<span class="ide-term-info">--- SOLUCAO DE REFERENCIA ---</span>';
            term.innerHTML += '\n<span class="ide-term-info">' + helpText + '</span>';
        }

        if (State.lockedRegion) {
            term.innerHTML += '\n<span class="ide-term-warn">Você continua dentro da empresa. Interaja com o fundador para tentar novamente.</span>';
        }

        // Do NOT mark _solved so IDE.close will not unlock
        setTimeout(() => this.close(), 3000);
    },

    close() {
        document.getElementById('ideOverlay').classList.remove('visible');
        document.getElementById('ideHelpOverlay').style.display = 'none';
        if (StudyChat.isOpen()) StudyChat.close();
        const wasSolved = this._solved;
        const regionBeingWorked = State.lockedRegion;
        this._currentChallenge = null;
        this._currentNpc = null;
        this._scalePlan = null;
        this._scalePasses = 0;
        this._scaleLastCode = '';
        this._baseChallengeDesc = '';
        State.isInChallenge = false;
        SFX.resumeMusic();

        // Check if all challenges in locked region are complete
        if (regionBeingWorked && wasSolved) {
            const regionTheory = State.challenges.filter(c => c.region === regionBeingWorked);
            const theoryDone = regionTheory.every(c => State.player.completed_challenges.includes(c.id));
            // IDE challenge is considered done if _solved was true
            if (theoryDone) {
                // Region fully completed -- unlock player
                State.completedRegions.push(regionBeingWorked);
                State.lockedRegion = null;
                State.lockedNpc = null;
                State.doorAnimBuilding = null;
                // Persist region completion immediately
                WorldStatePersistence.save(true);
                State.companyComplete = true;

                // Check if ALL 24 companies are now complete -> VICTORY
                if (_allCompaniesComplete()) {
                    setTimeout(() => { State.companyComplete = false; }, 1000);
                    setTimeout(() => UI.showVictory(State.player), 1500);
                } else {
                    World.showDialog('SISTEMA', regionBeingWorked,
                        'Parabéns! Você completou TODOS os desafios em ' + regionBeingWorked + '. Você está livre para explorar e coletar livros.');
                    setTimeout(() => { State.companyComplete = false; }, 3000);
                }
            }
        }
    },

    /**
     * Draw the player character on the small IDE canvas.
     * Simplified version of World.drawPlayer for a static portrait.
     */
    _drawPlayerChar() {
        const canvas = document.getElementById('idePlayerCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const skinIdx = State.avatarIndex || 0;
        const skinColor = World.getSkinColor ? World.getSkinColor(skinIdx) : '#F5D0A9';

        // Simple standing character (no animation)
        const cx = w / 2, bodyTop = 24;

        // Head
        ctx.fillStyle = skinColor;
        ctx.beginPath();
        ctx.arc(cx, 14, 11, 0, Math.PI * 2);
        ctx.fill();

        // Hair
        ctx.fillStyle = '#1a1a2e';
        ctx.beginPath();
        ctx.arc(cx, 11, 11.5, Math.PI, Math.PI * 2);
        ctx.fill();
        if (skinIdx >= 2) {
            ctx.fillRect(cx - 12, 12, 4, 20);
            ctx.fillRect(cx + 8, 12, 4, 20);
        }

        // Eyes
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(cx - 4, 15, 3, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 4, 15, 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#111';
        ctx.beginPath(); ctx.arc(cx - 3, 15.5, 1.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 5, 15.5, 1.5, 0, Math.PI * 2); ctx.fill();

        // Mouth (smile)
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, 19, 3, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();

        // Body
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(cx - 10, bodyTop, 20, 24);

        // Shirt text 'Garage'
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 5px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Garage', cx, bodyTop + 12);

        // Arms
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(cx - 14, bodyTop + 2, 5, 14);
        ctx.fillRect(cx + 9, bodyTop + 2, 5, 14);
        ctx.fillStyle = skinColor;
        ctx.fillRect(cx - 14, bodyTop + 16, 5, 8);
        ctx.fillRect(cx + 9, bodyTop + 16, 5, 8);

        // Legs
        ctx.fillStyle = '#4472C4';
        ctx.fillRect(cx - 8, bodyTop + 24, 7, 20);
        ctx.fillRect(cx + 1, bodyTop + 24, 7, 20);

        // Shoes
        ctx.fillStyle = '#e5e7eb';
        ctx.fillRect(cx - 9, bodyTop + 43, 9, 5);
        ctx.fillRect(cx + 1, bodyTop + 43, 9, 5);
    },

    /**
     * Draw the NPC mentor on the small IDE canvas.
     * Uses NPC look data for distinctive features.
     */
    _drawMentorChar() {
        const canvas = document.getElementById('ideMentorCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const npc = this._currentNpc;
        if (!npc) return;

        const look = npc.look || {};
        const skinColor = look.skinTone || '#F5D0A9';
        const cx = w / 2, bodyTop = 24;

        // Head
        ctx.fillStyle = skinColor;
        ctx.beginPath();
        ctx.arc(cx, 14, 11, 0, Math.PI * 2);
        ctx.fill();

        // Hair
        if (look.hair && look.hairStyle !== 'bald') {
            ctx.fillStyle = look.hair;
            ctx.beginPath();
            ctx.arc(cx, 11, 11.5, Math.PI, Math.PI * 2);
            ctx.fill();
        }

        // Beard
        if (look.beard) {
            ctx.fillStyle = look.beard;
            ctx.beginPath();
            ctx.moveTo(cx - 7, 18);
            ctx.quadraticCurveTo(cx, 28, cx + 7, 18);
            ctx.fill();
        }

        // Glasses
        if (look.glasses) {
            ctx.strokeStyle = '#555';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.arc(cx - 5, 14, 4, 0, Math.PI * 2);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(cx + 5, 14, 4, 0, Math.PI * 2);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(cx - 1, 14);
            ctx.lineTo(cx + 1, 14);
            ctx.stroke();
        }

        // Eyes
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(cx - 4, 14, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 4, 14, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#111';
        ctx.beginPath(); ctx.arc(cx - 4, 14.5, 1.2, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 4, 14.5, 1.2, 0, Math.PI * 2); ctx.fill();

        // Mouth
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, 19, 3, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();

        // Body (shirt)
        const shirtColor = look.shirt || '#3b82f6';
        ctx.fillStyle = look.turtleneck ? '#111' : shirtColor;
        ctx.fillRect(cx - 10, bodyTop, 20, 24);

        // Turtleneck collar
        if (look.turtleneck) {
            ctx.fillStyle = '#111';
            ctx.fillRect(cx - 6, bodyTop - 3, 12, 6);
        }

        // Tie
        if (look.tie) {
            ctx.fillStyle = look.tie;
            ctx.beginPath();
            ctx.moveTo(cx, bodyTop);
            ctx.lineTo(cx - 3, bodyTop + 12);
            ctx.lineTo(cx, bodyTop + 18);
            ctx.lineTo(cx + 3, bodyTop + 12);
            ctx.closePath();
            ctx.fill();
        }

        // Hoodie hood line
        if (look.hoodie) {
            ctx.strokeStyle = look.hoodie;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(cx, bodyTop - 2, 12, 0.8 * Math.PI, 0.2 * Math.PI);
            ctx.stroke();
        }

        // Arms
        ctx.fillStyle = look.turtleneck ? '#111' : shirtColor;
        ctx.fillRect(cx - 14, bodyTop + 2, 5, 14);
        ctx.fillRect(cx + 9, bodyTop + 2, 5, 14);
        ctx.fillStyle = skinColor;
        ctx.fillRect(cx - 14, bodyTop + 16, 5, 8);
        ctx.fillRect(cx + 9, bodyTop + 16, 5, 8);

        // Legs
        ctx.fillStyle = look.pants || '#333';
        ctx.fillRect(cx - 8, bodyTop + 24, 7, 20);
        ctx.fillRect(cx + 1, bodyTop + 24, 7, 20);

        // Shoes
        ctx.fillStyle = '#222';
        ctx.fillRect(cx - 9, bodyTop + 43, 9, 5);
        ctx.fillRect(cx + 1, bodyTop + 43, 9, 5);
    },
};

// ---- auth module ----
const Auth = {
    _user: null,
    _token: null,
    _refreshToken: null,
    _refreshing: null,

    init() {
        const stored = localStorage.getItem('garage_user');
        const token = localStorage.getItem('garage_token');
        const refresh = localStorage.getItem('garage_refresh');
        if (stored && token) {
            try {
                this._user = JSON.parse(stored);
                this._token = token;
                this._refreshToken = refresh;
            } catch (e) {
                this._user = null;
                this._token = null;
                this._refreshToken = null;
            }
        }
        // Migrate from sessionStorage (one-time)
        if (!this._token) {
            const legacyToken = sessionStorage.getItem('garage_token');
            const legacyUser = sessionStorage.getItem('garage_user');
            const legacyRefresh = sessionStorage.getItem('garage_refresh');
            if (legacyToken && legacyUser) {
                try {
                    this._user = JSON.parse(legacyUser);
                    this._token = legacyToken;
                    this._refreshToken = legacyRefresh;
                    this._persist();
                } catch (e) { /* ignore */ }
                sessionStorage.removeItem('garage_token');
                sessionStorage.removeItem('garage_user');
                sessionStorage.removeItem('garage_refresh');
            }
        }
        this._bindForms();
        this._bindNavigation();
    },

    isLoggedIn() {
        return this._user !== null && this._token !== null;
    },

    getUser() {
        return this._user;
    },

    getToken() {
        return this._token;
    },

    hasSession() {
        return !!localStorage.getItem('garage_session_id');
    },

    isAdmin() {
        if (!this._token) return false;
        try {
            const parts = this._token.split('.');
            if (parts.length < 2) return false;
            const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
            const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
            const payload = JSON.parse(atob(padded));
            return payload.role === 'admin';
        } catch (_e) {
            return false;
        }
    },

    _persist() {
        if (this._user) localStorage.setItem('garage_user', JSON.stringify(this._user));
        if (this._token) localStorage.setItem('garage_token', this._token);
        if (this._refreshToken) localStorage.setItem('garage_refresh', this._refreshToken);
    },

    _setUser(user, accessToken, refreshToken) {
        this._user = user;
        this._token = accessToken;
        this._refreshToken = refreshToken || null;
        this._persist();
    },

    logout() {
        // Reset pause state before leaving the world screen
        if (State.paused) {
            State.paused = false;
            const po = document.getElementById('pauseOverlay');
            if (po) po.style.display = 'none';
        }
        if (typeof StudyChat !== 'undefined' && StudyChat.isOpen()) {
            StudyChat.close();
        }
        if (typeof Learning !== 'undefined' && Learning.isOpen()) {
            Learning.cancel();
        }
        // Stop heartbeat when logging out
        if (typeof Heartbeat !== 'undefined') {
            Heartbeat.stop();
        }
        // Stop world state persistence
        if (typeof WorldStatePersistence !== 'undefined') {
            WorldStatePersistence.stopPeriodicSave();
        }
        this._user = null;
        this._token = null;
        this._refreshToken = null;
        localStorage.removeItem('garage_user');
        localStorage.removeItem('garage_token');
        localStorage.removeItem('garage_refresh');
        localStorage.removeItem('garage_session_id');
        UI.showScreen('screen-login');
    },

    async tryRefresh() {
        if (!this._refreshToken) return false;
        if (this._refreshing) return this._refreshing;
        this._refreshing = (async () => {
            try {
                const r = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: this._refreshToken }),
                });
                if (!r.ok) return false;
                const data = await r.json();
                this._token = data.access_token;
                localStorage.setItem('garage_token', this._token);
                return true;
            } catch (e) {
                return false;
            } finally {
                this._refreshing = null;
            }
        })();
        return this._refreshing;
    },

    handleExpired() {
        if (typeof StudyChat !== 'undefined' && StudyChat.isOpen()) {
            StudyChat.close();
        }
        if (typeof Learning !== 'undefined' && Learning.isOpen()) {
            Learning.cancel();
        }
        this._user = null;
        this._token = null;
        this._refreshToken = null;
        localStorage.removeItem('garage_user');
        localStorage.removeItem('garage_token');
        localStorage.removeItem('garage_refresh');
        localStorage.removeItem('garage_session_id');
    },

    _bindNavigation() {
        const goReg = document.getElementById('goToRegister');
        const goLog = document.getElementById('goToLogin');
        if (goReg) goReg.addEventListener('click', (e) => { e.preventDefault(); UI.showScreen('screen-register'); });
        if (goLog) goLog.addEventListener('click', (e) => { e.preventDefault(); UI.showScreen('screen-login'); });
    },

    _bindForms() {
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');

        if (loginForm) loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errEl = document.getElementById('loginError');
            errEl.hidden = true;
            const btn = loginForm.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.textContent = 'ENTRANDO...';

            try {
                const res = await API.post('/api/auth/login', {
                    username: document.getElementById('loginUsername').value.trim(),
                    password: document.getElementById('loginPassword').value,
                });
                this._setUser(res.user, res.access_token, res.refresh_token);
                UI.showScreen('screen-title');
            } catch (err) {
                errEl.textContent = err.message || 'Erro ao fazer login.';
                errEl.hidden = false;
            } finally {
                btn.disabled = false;
                btn.textContent = 'ENTRAR';
            }
        });

        if (registerForm) registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errEl = document.getElementById('registerError');
            const sucEl = document.getElementById('registerSuccess');
            errEl.hidden = true;
            sucEl.hidden = true;
            const btn = registerForm.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.textContent = 'CADASTRANDO...';

            try {
                const pwd = document.getElementById('regPassword').value;
                const pwdConfirm = document.getElementById('regPasswordConfirm').value;
                if (pwd !== pwdConfirm) {
                    throw new Error('As senhas não coincidem.');
                }
                const res = await API.post('/api/auth/register', {
                    full_name: document.getElementById('regFullName').value.trim(),
                    username: document.getElementById('regUsername').value.trim(),
                    email: document.getElementById('regEmail').value.trim(),
                    whatsapp: document.getElementById('regWhatsapp').value.trim(),
                    profession: document.getElementById('regProfession').value,
                    password: pwd,
                });
                this._setUser(res.user, res.access_token, res.refresh_token);
                sucEl.textContent = 'Cadastro realizado! Entrando...';
                sucEl.hidden = false;
                setTimeout(() => UI.showScreen('screen-title'), 1200);
            } catch (err) {
                errEl.textContent = err.message || 'Erro ao cadastrar.';
                errEl.hidden = false;
            } finally {
                btn.disabled = false;
                btn.textContent = 'CADASTRAR';
            }
        });
    },
};

// ---- boot ----
document.addEventListener('DOMContentLoaded', async () => {
    Auth.init();
    if (Auth.isLoggedIn()) {
        // Validate token with server before auto-resuming
        try {
            await API.get('/api/auth/me');
        } catch (_e) {
            // Token invalid or server unreachable -- force login
            Auth.handleExpired();
            UI.showScreen('screen-login');
            return;
        }
        if (Auth.hasSession()) {
            const resumed = await Game.loadSession(true);
            if (!resumed) {
                // loadSession may have cleared auth on 401
                if (!Auth.isLoggedIn()) {
                    UI.showScreen('screen-login');
                } else {
                    UI.showScreen('screen-title');
                    UI.updateTitleButtons();
                }
            }
        } else {
            UI.showScreen('screen-title');
            UI.updateTitleButtons();
        }
    } else {
        UI.showScreen('screen-login');
    }
});

// Save world state before page unload
window.addEventListener('beforeunload', () => {
    if (State.sessionId) {
        // Use sendBeacon for reliable delivery during page unload
        const data = {
            session_id: State.sessionId,
            collected_books: [...State.collectedBooks],
            completed_regions: [...State.completedRegions],
            current_region: State.lockedRegion,
            player_world_x: World.player ? Math.round(World.player.x) : 100,
        };
        const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
        const token = Auth.getToken();
        // Use fetch with keepalive for authenticated request during unload
        if (token) {
            navigator.sendBeacon('/api/save-world-state-beacon', blob);
        }
    }
});

// Also save on visibility change (tab hidden, mobile app backgrounded)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && State.sessionId) {
        WorldStatePersistence.save(true);
    }
});
