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
    sfxVol: 0.04,

    _init() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterVol = this.ctx.createGain();
            this.masterVol.gain.value = 0.5;
            this.masterVol.connect(this.ctx.destination);
            this.musicGain = this.ctx.createGain();
            this.musicGain.gain.value = 1.0;
            this.musicGain.connect(this.masterVol);
        }
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
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, speed * 0.9 / 1000, type || 'sine', vol || 0.03, 1500), i * speed));
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
        this._lofiTone(90, 0.05, 'sine', 0.025, 600);
    },

    step() { this._lofiTone(100 + Math.random() * 20, 0.025, 'sine', 0.012, 500); },
    run() { this._lofiTone(140 + Math.random() * 30, 0.02, 'sine', 0.01, 600); },

    talk() {
        const notes = [330, 392, 349, 440, 370];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.035, 'sine', 0.025, 1200), i * 55));
    },

    correct() {
        this._arpeggio([523, 659, 784], 100, 'sine', 0.035);
        setTimeout(() => this._lofiTone(1047, 0.3, 'sine', 0.025, 1500), 350);
    },

    wrong() {
        this._lofiTone(250, 0.15, 'triangle', 0.03, 800);
        setTimeout(() => this._lofiTone(180, 0.2, 'triangle', 0.025, 600), 160);
    },

    promote() {
        const notes = [392, 440, 523, 659, 784];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.25, 'sine', 0.035, 1400), i * 140));
        setTimeout(() => {
            [262, 330, 392].forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.35, 'triangle', 0.02, 800), i * 180));
        }, 80);
    },

    bookCollect() {
        this._init();
        const notes = [659, 784, 988, 1319];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.1, 'sine', 0.03, 1800), i * 60));
        setTimeout(() => this._lofiTone(1568, 0.25, 'sine', 0.02, 1200), 280);
    },

    npcInteract() {
        this._arpeggio([349, 440, 523], 70, 'sine', 0.03);
    },

    gameOver() {
        const notes = [392, 349, 330, 294, 262];
        notes.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.3, 'triangle', 0.03, 700), i * 200));
    },

    victory() {
        const melody = [523, 659, 784, 1047, 784, 1047, 1319];
        melody.forEach((f, i) => setTimeout(() => this._lofiTone(f, 0.2, 'sine', 0.03, 1600), i * 150));
    },

    menuSelect() {
        this._lofiTone(600, 0.05, 'sine', 0.025, 1500);
        setTimeout(() => this._lofiTone(900, 0.06, 'sine', 0.02, 1200), 50);
    },

    menuConfirm() {
        this._arpeggio([440, 659, 880], 55, 'sine', 0.03);
    },

    challengeOpen() {
        this._arpeggio([330, 392, 494, 587], 80, 'sine', 0.025);
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
        this._init();
        this._currentPhase = phase;
        this._musicPlaying = true;

        if (phase === 'title') {
            this._playArcade();
        } else {
            this._playLofi(phase);
        }
    },

    stopMusic() {
        this._musicPlaying = false;
        this._currentPhase = null;
        this._musicPaused = false;
        clearTimeout(this._musicTimer);
        this._musicNodes.forEach(n => { try { n.stop(); } catch (e) { } });
        this._musicNodes = [];
        this._crackleNode = null;
    },

    /** Fade out music gain to silence without destroying nodes (seamless resume). */
    pauseMusic() {
        if (!this.ctx || !this.musicGain || this._musicPaused) return;
        this._musicPaused = true;
        const t = this.ctx.currentTime;
        this.musicGain.gain.cancelScheduledValues(t);
        this.musicGain.gain.setValueAtTime(this.musicGain.gain.value, t);
        this.musicGain.gain.linearRampToValueAtTime(0.0001, t + 0.3);
    },

    /** Fade music gain back in (seamless resume after pause). */
    resumeMusic() {
        if (!this.ctx || !this.musicGain || !this._musicPaused) return;
        this._musicPaused = false;
        const t = this.ctx.currentTime;
        this.musicGain.gain.cancelScheduledValues(t);
        this.musicGain.gain.setValueAtTime(this.musicGain.gain.value, t);
        this.musicGain.gain.linearRampToValueAtTime(1.0, t + 0.3);
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
};

// ---- NPC definitions ----
const NPC_DATA = [
    // -- INTERN --
    {
        id: 'npc_xerox', name: 'CHARLES GESCHKE', role: 'Cofundador - Xerox PARC / Adobe', region: 'Xerox PARC', stage: 'Intern', worldX: 800,
        dialog: 'Eu sou Charles Geschke. Nos anos 70, a Xerox PARC inventou a interface grafica, o mouse e a rede Ethernet -- tecnologias que mudaram o mundo. Mais tarde cofundei a Adobe e criamos o PostScript e o PDF. Aqui voce vai provar que domina os fundamentos: logica, variaveis e estruturas basicas. Sem base solida, nenhum sistema sobrevive.',
        look: { hair: '#ccc', hairStyle: 'bald-sides', beard: '#aaa', glasses: true, glassesStyle: 'round', shirt: '#1e3a5f', pants: '#333', skinTone: '#F5D0A9' }
    },
    {
        id: 'npc_apple', name: 'STEVE JOBS', role: 'Cofundador - Apple', region: 'Apple Garage', stage: 'Intern', worldX: 1800,
        dialog: 'Sou Steve Jobs. Em 1976, Steve Wozniak e eu montamos o primeiro Apple numa garagem em Los Altos, California. A Apple revolucionou a computacao pessoal, a musica digital e os smartphones. Eu acreditava que tecnologia e arte devem andar juntas. Seus desafios aqui testarao sua capacidade de pensar simples -- porque simplicidade e a sofisticacao suprema.',
        look: { hair: '#222', hairStyle: 'short', beard: null, glasses: true, glassesStyle: 'round', shirt: '#111', pants: '#3b5998', skinTone: '#F5D0A9', turtleneck: true }
    },
    // -- JUNIOR --
    {
        id: 'npc_microsoft', name: 'BILL GATES', role: 'Cofundador - Microsoft', region: 'Microsoft', stage: 'Junior', worldX: 3200,
        dialog: 'Prazer, Bill Gates. Em 1975, Paul Allen e eu fundamos a Microsoft com a visao de colocar um computador em cada mesa. Do MS-DOS ao Windows, do Office ao Azure -- construimos um ecossistema que conecta bilhoes de pessoas. Como Junior, voce precisa provar que entende sistemas operacionais, estruturas de dados e a base da engenharia de software.',
        look: { hair: '#8B6F47', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#4a90d9', pants: '#2c3e50', skinTone: '#F5D0A9', tie: '#8b0000' }
    },
    {
        id: 'npc_nubank', name: 'DAVID VELEZ', role: 'Fundador - Nubank', region: 'Nubank', stage: 'Junior', worldX: 4400,
        dialog: 'Ola, sou David Velez. Fundei o Nubank em 2013 no Brasil porque estava cansado da burocracia bancaria. Com um cartao roxo e um app, democratizamos servicos financeiros para mais de 80 milhoes de clientes. Fintech e sobre eliminar complexidade e entregar valor real. Mostre que voce sabe resolver problemas com codigo limpo e eficiente.',
        look: { hair: '#222', hairStyle: 'short', beard: null, glasses: false, shirt: '#820ad1', pants: '#222', skinTone: '#D2A673', casual: true }
    },
    // -- MID --
    {
        id: 'npc_google', name: 'LARRY & SERGEY', role: 'Cofundadores - Google', region: 'Google', stage: 'Mid', worldX: 5800,
        dialog: 'Somos Larry Page e Sergey Brin. Em 1998, numa garagem em Menlo Park, criamos o Google -- um buscador que organizou toda a informacao do mundo. Depois veio o Android, YouTube, Cloud, IA. Como engenheiro Pleno, voce enfrentara algoritmos avancados, sistemas distribuidos e a complexidade computacional que faz o Google funcionar em escala planetaria.',
        look: { hair: '#333', hairStyle: 'curly', beard: null, glasses: false, shirt: '#4285f4', pants: '#333', skinTone: '#F5D0A9', casual: true }
    },
    {
        id: 'npc_facebook', name: 'MARK ZUCKERBERG', role: 'Cofundador - Facebook', region: 'Facebook', stage: 'Mid', worldX: 7300,
        dialog: 'Eu sou Mark Zuckerberg. Em 2004, no dormitorio de Harvard, criei o Facebook. Hoje a Meta conecta mais de 3 bilhoes de pessoas e esta construindo o metaverso. Escalar grafos sociais para esse volume exige engenharia de dados, consistencia eventual e arquitetura de sistemas que nao falham. Prepare-se para desafios de nivel Pleno.',
        look: { hair: '#8B6F47', hairStyle: 'curly-short', beard: null, glasses: false, shirt: '#888', pants: '#333', skinTone: '#F5D0A9', hoodie: '#444' }
    },
    // -- SENIOR --
    {
        id: 'npc_amazon', name: 'JEFF BEZOS', role: 'Fundador - Amazon', region: 'Amazon', stage: 'Senior', worldX: 8800,
        dialog: 'Jeff Bezos aqui. Comecei a Amazon em 1994 vendendo livros numa garagem em Seattle. Hoje somos o maior e-commerce do planeta e a AWS e a espinha dorsal da internet moderna. De e-commerce a cloud computing, aqui voce projetara sistemas resilientes, com tolerancia a falhas e alta disponibilidade. Engenheiro Senior nao aceita sistema que cai.',
        look: { hair: null, hairStyle: 'bald', beard: null, glasses: false, shirt: '#1a3c5e', pants: '#222', skinTone: '#F5D0A9', bald: true }
    },
    {
        id: 'npc_meli', name: 'MARCOS GALPERIN', role: 'Fundador - Mercado Livre', region: 'Mercado Livre', stage: 'Senior', worldX: 10200,
        dialog: 'Sou Marcos Galperin. Fundei o Mercado Livre em 1999 na Argentina. Somos o maior ecossistema de comercio eletronico da America Latina -- marketplace, pagamentos com Mercado Pago, logistica e credito. Processamos milhoes de transacoes por segundo em 18 paises. Seus desafios aqui envolvem escala, performance e arquitetura de plataforma.',
        look: { hair: '#555', hairStyle: 'short', beard: null, glasses: false, shirt: '#333', pants: '#222', skinTone: '#F5D0A9', suit: '#1a1a1a' }
    },
    {
        id: 'npc_jpmorgan', name: 'JAMIE DIMON', role: 'CEO - JP Morgan', region: 'JP Morgan', stage: 'Senior', worldX: 11600,
        dialog: 'Jamie Dimon, CEO do JP Morgan Chase -- o maior banco dos Estados Unidos, com mais de 200 anos de historia. Wall Street exige zero tolerancia a falhas. Cada transacao financeira e irrevogavel, cada microsegundo conta. Aqui voce enfrentara desafios de sistemas criticos, concorrencia e seguranca de nivel bancario.',
        look: { hair: '#888', hairStyle: 'parted', beard: null, glasses: false, shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#0a3d62', tie: '#c9a800' }
    },
    // -- STAFF --
    {
        id: 'npc_tesla', name: 'ELON MUSK', role: 'CEO - Tesla / SpaceX', region: 'Tesla / SpaceX', stage: 'Staff', worldX: 13100,
        dialog: 'Elon Musk. Tesla revolucionou os carros eletricos, SpaceX esta tornando a humanidade multiplanetaria, e a Neuralink conecta cerebros a computadores. Engenharia extrema sob restricoes extremas -- esse e o padrao aqui. Como Staff Engineer, voce vai redesenhar sistemas complexos, otimizar para o impossivel e liderar decisoes tecnicas criticas.',
        look: { hair: '#555', hairStyle: 'short', beard: null, glasses: false, shirt: '#111', pants: '#222', skinTone: '#F5D0A9', jacket: '#1a1a1a' }
    },
    {
        id: 'npc_itau', name: 'ROBERTO SETUBAL', role: 'Ex-CEO - Itau Unibanco', region: 'Itau', stage: 'Staff', worldX: 14600,
        dialog: 'Roberto Setubal, ex-CEO do Itau Unibanco -- o maior banco privado do Brasil e da America Latina. Processamos trilhoes de reais por ano com sistemas que nao podem parar. A transformacao digital de um banco centenario exige migrar legados para arquiteturas modernas sem interromper operacoes. Desafios de Staff Engineer estao a sua espera.',
        look: { hair: '#aaa', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#003399', tie: '#ff6600' }
    },
    {
        id: 'npc_uber', name: 'TRAVIS KALANICK', role: 'Cofundador - Uber', region: 'Uber', stage: 'Staff', worldX: 16000,
        dialog: 'Travis Kalanick aqui. Cofundei a Uber em 2009 e transformamos o transporte global. Milhoes de corridas por minuto em centenas de cidades. Geolocalizacao em tempo real, matching de motoristas, precificacao dinamica, pagamentos -- tudo processado em milissegundos. Seus desafios envolvem sistemas real-time de altissima performance.',
        look: { hair: '#333', hairStyle: 'short', beard: null, glasses: false, shirt: '#111', pants: '#222', skinTone: '#F5D0A9', casual: true }
    },
    // -- PRINCIPAL --
    {
        id: 'npc_santander', name: 'ANA BOTIN', role: 'CEO - Santander', region: 'Santander', stage: 'Principal', worldX: 17400,
        dialog: 'Ana Botin, CEO do Grupo Santander -- um dos maiores bancos do mundo, presente em dezenas de paises. Banking global exige compliance com regulacoes como PCI DSS, PSD2, LGPD e Basel III simultaneamente. Zero margem de erro, auditoria total. Como Principal Engineer, seus desafios sao de governanca, seguranca e arquitetura regulatoria.',
        look: { hair: '#8B4513', hairStyle: 'parted', beard: null, glasses: false, shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#ec0000' }
    },
    {
        id: 'npc_bradesco', name: 'MARCELO NORONHA', role: 'CEO - Bradesco', region: 'Bradesco', stage: 'Principal', worldX: 18900,
        dialog: 'Marcelo Noronha, CEO do Bradesco. Somos um dos maiores bancos do Brasil, com mais de 70 milhoes de clientes. A transformacao digital de um banco dessa escala -- de agencias fisicas a APIs abertas, Open Banking e Pix -- exige visao arquitetural profunda. Seus desafios de Principal Engineer envolvem design de sistemas que definem o futuro financeiro.',
        look: { hair: '#555', hairStyle: 'parted', beard: null, glasses: true, glassesStyle: 'square', shirt: '#fff', pants: '#111', skinTone: '#F5D0A9', suit: '#cc092f', tie: '#cc092f' }
    },
    {
        id: 'npc_cloud', name: 'LINUS TORVALDS', role: 'Criador - Linux / Git', region: 'Cloud Valley', stage: 'Principal', worldX: 20400,
        dialog: 'Linus Torvalds. Criei o Linux em 1991, o sistema operacional que roda em servidores, smartphones e supercomputadores. Depois criei o Git, que revolucionou o controle de versao. Voce chegou ao topo da jornada. Aqui criamos contratos para o futuro -- open source, infraestrutura global e os alicerces da computacao moderna.',
        look: { hair: '#c4a35a', hairStyle: 'short', beard: '#b8963e', glasses: true, glassesStyle: 'square', shirt: '#2d5016', pants: '#3b3b3b', skinTone: '#F5D0A9' }
    },
];

// ---- buildings / zones ----
const BUILDINGS = [
    { name: 'XEROX PARC', x: 500, w: 400, h: 200, color: '#94a3b8', roofColor: '#64748b' },
    { name: 'APPLE GARAGE', x: 1500, w: 350, h: 160, color: '#ef4444', roofColor: '#b91c1c' },
    { name: 'MICROSOFT', x: 2900, w: 500, h: 280, color: '#0078d4', roofColor: '#005a9e' },
    { name: 'NUBANK', x: 4100, w: 420, h: 240, color: '#820ad1', roofColor: '#5b0894' },
    { name: 'GOOGLE', x: 5500, w: 550, h: 250, color: '#4285f4', roofColor: '#2b5ea7' },
    { name: 'FACEBOOK', x: 7000, w: 450, h: 260, color: '#1877f2', roofColor: '#0d5bbd' },
    { name: 'AMAZON', x: 8500, w: 500, h: 300, color: '#ff9900', roofColor: '#cc7a00' },
    { name: 'MERCADO LIVRE', x: 9900, w: 480, h: 270, color: '#ffe600', roofColor: '#ccb800' },
    { name: 'JP MORGAN', x: 11300, w: 520, h: 310, color: '#0a3d62', roofColor: '#072a44' },
    { name: 'TESLA / SPACEX', x: 12800, w: 600, h: 320, color: '#cc0000', roofColor: '#990000' },
    { name: 'ITAU', x: 14300, w: 460, h: 280, color: '#003399', roofColor: '#002266' },
    { name: 'UBER', x: 15700, w: 440, h: 260, color: '#000000', roofColor: '#1a1a1a' },
    { name: 'SANTANDER', x: 17100, w: 500, h: 290, color: '#ec0000', roofColor: '#b30000' },
    { name: 'BRADESCO', x: 18600, w: 480, h: 280, color: '#cc092f', roofColor: '#990720' },
    { name: 'CLOUD VALLEY', x: 20100, w: 650, h: 350, color: '#8b5cf6', roofColor: '#6d28d9' },
];

// ---- collectible books ----
const BOOKS_DATA = [
    {
        id: 'b01', title: 'Clean Code', author: 'Robert C. Martin', color: '#22c55e',
        summary: 'Codigo e um ativo de longo prazo. Legibilidade > esperteza. Funcoes pequenas, nomes claros, responsabilidade unica e testes automatizados.',
        lesson: 'Codigo e para humanos primeiro; manutencao custa mais que escrever.',
        worldX: 400, floatY: 130
    },
    {
        id: 'b02', title: 'The Clean Coder', author: 'Robert C. Martin', color: '#16a34a',
        summary: 'Profissionalismo em engenharia. Disciplina, estimativas realistas, dizer "nao", foco, pratica deliberada e responsabilidade pessoal pela qualidade.',
        lesson: 'Ser senior nao e saber mais tecnologia, e assumir compromisso com entrega previsivel e qualidade.',
        worldX: 700, floatY: 150
    },
    {
        id: 'b03', title: 'Clean Architecture', author: 'Robert C. Martin', color: '#15803d',
        summary: 'Arquitetura orientada a independencia: do framework, do banco, da UI e de detalhes externos. Dependencias apontam para o dominio.',
        lesson: 'O negocio e o nucleo; tecnologia e detalhe substituivel.',
        worldX: 1200, floatY: 140
    },
    {
        id: 'b04', title: 'Design Patterns', author: 'GoF (Gang of Four)', color: '#3b82f6',
        summary: 'Catalogo de solucoes recorrentes para problemas classicos de design orientado a objetos. Ensina quando abstrair, desacoplar e reutilizar.',
        lesson: 'Nao reinventar a roda; use padroes para reduzir complexidade e acoplamento.',
        worldX: 2000, floatY: 160
    },
    {
        id: 'b05', title: 'Refactoring', author: 'Martin Fowler', color: '#6366f1',
        summary: 'Melhorar codigo sem alterar comportamento. Pequenas mudancas continuas mantem o sistema saudavel.',
        lesson: 'Divida tecnica cresce em silencio; refatorar e manutencao estrategica, nao luxo.',
        worldX: 2600, floatY: 130
    },
    {
        id: 'b06', title: 'Domain-Driven Design', author: 'Eric Evans', color: '#8b5cf6',
        summary: 'Modelar software a partir do dominio do negocio, usando linguagem ubiqua e limites claros (Bounded Contexts).',
        lesson: 'Software complexo falha quando a tecnologia ignora o negocio.',
        worldX: 3500, floatY: 150
    },
    {
        id: 'b07', title: 'Implementing DDD', author: 'Vaughn Vernon', color: '#7c3aed',
        summary: 'Versao pratica do DDD: agregados, eventos de dominio, consistencia, microsservicos orientados a contexto.',
        lesson: 'Limites bem definidos evitam sistemas distribuidos caoticos.',
        worldX: 4200, floatY: 140
    },
    {
        id: 'b08', title: 'Designing Data-Intensive Apps', author: 'Martin Kleppmann', color: '#ef4444',
        summary: 'Biblia de sistemas distribuidos: consistencia, replicacao, particionamento, tolerancia a falhas, trade-offs CAP.',
        lesson: 'Escala e sobre trade-offs; nao existe sistema distribuido perfeito.',
        worldX: 5100, floatY: 160
    },
    {
        id: 'b09', title: 'Building Microservices', author: 'Sam Newman', color: '#f97316',
        summary: 'Como decompor sistemas, evitar acoplamento e gerenciar comunicacao, deploy e governanca.',
        lesson: 'Microsservicos so funcionam com autonomia, observabilidade e cultura madura.',
        worldX: 5700, floatY: 130
    },
    {
        id: 'b10', title: 'Release It!', author: 'Michael Nygard', color: '#dc2626',
        summary: 'Sistemas falham em producao por causas previsiveis. Circuit breaker, bulkhead, retry, timeout e padroes de resiliencia.',
        lesson: 'Projetar para falhar e o unico caminho para estabilidade.',
        worldX: 6500, floatY: 150
    },
    {
        id: 'b11', title: 'Site Reliability Engineering', author: 'Google SRE Team', color: '#fbbf24',
        summary: 'Operar sistemas como engenharia: SLO, error budget, automacao, reducao de toil.',
        lesson: 'Confiabilidade e uma metrica de negocio, nao apenas tecnica.',
        worldX: 7200, floatY: 140
    },
    {
        id: 'b12', title: 'The Phoenix Project', author: 'Gene Kim', color: '#f59e0b',
        summary: 'Romance sobre transformacao DevOps. Mostra gargalos, fluxo, dependencias e melhoria continua.',
        lesson: 'TI e sistema de producao; otimizar o fluxo gera resultado real.',
        worldX: 8200, floatY: 160
    },
    {
        id: 'b13', title: 'The DevOps Handbook', author: 'Gene Kim', color: '#eab308',
        summary: 'Manual pratico: CI/CD, infraestrutura como codigo, feedback rapido, cultura colaborativa.',
        lesson: 'Velocidade com qualidade so vem com automacao e integracao continua.',
        worldX: 9500, floatY: 130
    },
    {
        id: 'b14', title: 'The Lean Startup', author: 'Eric Ries', color: '#ec4899',
        summary: 'Construir, medir, aprender. Validar hipoteses antes de escalar.',
        lesson: 'Nao construa mais; aprenda mais rapido com o mercado.',
        worldX: 10200, floatY: 150
    },
    {
        id: 'b15', title: 'Measure What Matters', author: 'John Doerr', color: '#d946ef',
        summary: 'OKRs para alinhar estrategia e execucao. Foco em resultados mensuraveis e prioridades claras.',
        lesson: 'O que nao e medido nao e gerenciado.',
        worldX: 11200, floatY: 140
    },
    {
        id: 'b16', title: 'Good Strategy Bad Strategy', author: 'Richard Rumelt', color: '#a855f7',
        summary: 'Estrategia real e diagnostico + escolha clara + acoes coerentes. Evita metas genericas e slogans.',
        lesson: 'Estrategia e foco e renuncia, nao ambicao vaga.',
        worldX: 12800, floatY: 160
    },
    {
        id: 'b17', title: 'Cracking the Coding Interview', author: 'Gayle Laakmann McDowell', color: '#06b6d4',
        summary: 'Preparacao para entrevistas tecnicas: arrays, strings, arvores, grafos, recursao e complexidade algoritmica.',
        lesson: 'Entrevistas medem raciocinio, nao decoreba. Pratique decomposicao de problemas.',
        worldX: 13500, floatY: 130
    },
    {
        id: 'b18', title: 'Introduction to Algorithms', author: 'Cormen, Leiserson, Rivest, Stein', color: '#0891b2',
        summary: 'CLRS: a referencia academica em algoritmos. Ordenacao, grafos, programacao dinamica, NP-completude.',
        lesson: 'Complexidade computacional define os limites do que e possivel.',
        worldX: 14500, floatY: 150
    },
    {
        id: 'b19', title: 'System Design Interview', author: 'Alex Xu', color: '#14b8a6',
        summary: 'Como projetar sistemas escalaveis: load balancer, cache, CDN, sharding, message queue, rate limiter.',
        lesson: 'Design de sistemas e sobre trade-offs mensuráveis, nao escolhas absolutas.',
        worldX: 15500, floatY: 140
    },
    {
        id: 'b20', title: 'Grokking Algorithms', author: 'Aditya Bhargava', color: '#10b981',
        summary: 'Algoritmos explicados visualmente: busca binaria, BFS, Dijkstra, programacao dinamica, KNN.',
        lesson: 'Pensar algoritmicamente e mais importante que decorar implementacoes.',
        worldX: 16500, floatY: 160
    },
    {
        id: 'b21', title: 'Accelerate', author: 'Forsgren, Humble, Kim', color: '#84cc16',
        summary: 'Metricas DORA: frequencia de deploy, lead time, MTTR, taxa de falha. Evidencia cientifica para DevOps.',
        lesson: 'Performance de engenharia se mede com dados, nao opiniao.',
        worldX: 17500, floatY: 130
    },
    {
        id: 'b22', title: 'Staff Engineer', author: 'Will Larson', color: '#a3e635',
        summary: 'Alem de senior: influencia tecnica, mentoria, decisoes arquiteturais, navegacao organizacional.',
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

// ---- world engine (canvas side-scroller) ----
const World = {
    canvas: null,
    ctx: null,
    W: 0,
    H: 0,
    GROUND_Y: 0,
    WORLD_WIDTH: 21500,
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

    init(avatarIndex) {
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

        // Reset player
        this.player.x = 100;
        this.player.y = 0;
        this.player.vx = 0;
        this.player.vy = 0;
        this.player.onGround = true;
        this.player.facing = 1;
        this.player.state = 'idle';
        this.camera.x = 0;
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
            // If IDE overlay is open, let the textarea handle all input
            const ideOpen = document.getElementById('ideOverlay') && document.getElementById('ideOverlay').classList.contains('visible');
            if (ideOpen) return;

            this.keys[e.code] = true;
            if (e.code === 'Enter' || e.code === 'Space') {
                if (State.isBookPopup) { this.closeBookPopup(); }
                else if (State.isInDialog) { this.closeDialog(); }
                else if (!State.isInChallenge) { this.tryInteract(); }
            }
            // Prevent scroll
            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
        });
        document.addEventListener('keyup', e => {
            const ideOpen = document.getElementById('ideOverlay') && document.getElementById('ideOverlay').classList.contains('visible');
            if (ideOpen) return;
            this.keys[e.code] = false;
        });

        // Mobile buttons -- hold-to-move with touchcancel safety
        const hold = (id, code) => {
            const el = document.getElementById(id);
            if (!el) return;
            const on = () => { this.keys[code] = true; el.classList.add('pressed'); };
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
                if (State.isBookPopup) this.closeBookPopup();
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
        if (State.isInChallenge || State.isInDialog || State.enteringDoor) return;
        if (!State.interactionTarget) return;
        // If already locked in a company, prevent interaction with other NPCs
        if (State.lockedRegion && State.interactionTarget.region !== State.lockedRegion) {
            this.showDialog('SISTEMA', 'Bloqueado', 'Voce precisa concluir todos os desafios em ' + State.lockedRegion + ' antes de sair. Resolva as questoes e o desafio de codigo.');
            return;
        }

        const npc = State.interactionTarget;
        const stageOrder = ['Intern', 'Junior', 'Mid', 'Senior', 'Staff', 'Principal', 'Distinguished'];
        const playerIdx = stageOrder.indexOf(State.player.stage);
        const npcIdx = stageOrder.indexOf(npc.stage);

        SFX.npcInteract();
        SFX.talk();

        if (npcIdx > playerIdx) {
            this.showDialog(npc.name, npc.role, 'Voce ainda nao atingiu o cargo necessario para me desafiar. Continue evoluindo.');
            return;
        }

        // If region already fully completed, just greet
        if (State.completedRegions.includes(npc.region)) {
            this.showDialog(npc.name, npc.role, 'Voce ja completou todos os desafios aqui. Parabens! Siga em frente para a proxima empresa.');
            return;
        }

        // If already locked in this same company, go directly to challenges (no door animation again)
        if (State.lockedRegion === npc.region) {
            State._pendingNpcRegion = npc.region;
            this.showDialog(npc.name, npc.role, 'Vamos continuar os desafios. Voce ainda precisa completar tudo aqui.');
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
                this.showDialog(npc.name, npc.role, npc.dialog + '\n\nVoce entrou na ' + npc.region + '. Resolva TODOS os desafios para poder sair.');
                State._pendingNpcRegion = npc.region;
            };
        } else {
            // Fallback if no building found
            State.lockedRegion = npc.region;
            State.lockedNpc = npc;
            this.showDialog(npc.name, npc.role, npc.dialog + '\n\nResolva TODOS os desafios para poder sair.');
            State._pendingNpcRegion = npc.region;
        }
    },

    showDialog(name, role, text) {
        State.isInDialog = true;
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
        if (State.isInDialog || State.isInChallenge || State.isBookPopup) return;

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
        this.update(dt);
        this.draw();
    },
};

// ---- UI ----
const UI = {
    showScreen(id) {
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
    },

    _drawOnboardingChar() {
        this._drawOnboardingBoy();
        this._drawOnboardingGirl();
    },

    _drawOnboardingBoy() {
        const canvas = document.getElementById('onboardingCharBoy');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const skinColor = '#F5D0A9';
        const cx = w / 2;
        const scale = 1.2;
        const offsetY = 10;

        ctx.save();
        ctx.translate(cx, offsetY);
        ctx.scale(scale, scale);
        const lx = 0;

        // Head
        ctx.fillStyle = skinColor;
        ctx.beginPath();
        ctx.arc(lx, 20, 16, 0, Math.PI * 2);
        ctx.fill();

        // Hair (dark, bowl cut)
        ctx.fillStyle = '#1a1a2e';
        ctx.beginPath();
        ctx.arc(lx, 16, 17, Math.PI, Math.PI * 2);
        ctx.fill();
        ctx.fillRect(lx - 17, 16, 4, 6);
        ctx.fillRect(lx + 13, 16, 4, 6);

        // Eyes (large, expressive)
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(lx - 6, 20, 5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(lx + 6, 20, 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#111';
        ctx.beginPath(); ctx.arc(lx - 5, 21, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(lx + 7, 21, 2.5, 0, Math.PI * 2); ctx.fill();

        // Mouth (smile)
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(lx, 28, 5, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();

        // Body (black tee)
        const bodyTop = 36;
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(lx - 14, bodyTop, 28, 30);

        // Shirt text 'Garage'
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 7px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Garage', lx, bodyTop + 15);

        // Arms
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(lx - 20, bodyTop + 2, 7, 18);
        ctx.fillRect(lx + 13, bodyTop + 2, 7, 18);
        ctx.fillStyle = skinColor;
        ctx.fillRect(lx - 20, bodyTop + 20, 7, 10);
        ctx.fillRect(lx + 13, bodyTop + 20, 7, 10);

        // Legs (blue jeans)
        ctx.fillStyle = '#4472C4';
        ctx.fillRect(lx - 11, bodyTop + 30, 10, 26);
        ctx.fillRect(lx + 1, bodyTop + 30, 10, 26);

        // Shoes (white sneakers)
        ctx.fillStyle = '#e5e7eb';
        ctx.fillRect(lx - 13, bodyTop + 55, 12, 6);
        ctx.fillRect(lx + 1, bodyTop + 55, 12, 6);

        ctx.restore();
    },

    _drawOnboardingGirl() {
        const canvas = document.getElementById('onboardingCharGirl');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const skinColor = '#F5D0A9';
        const cx = w / 2;
        const scale = 1.2;
        const offsetY = 10;

        ctx.save();
        ctx.translate(cx, offsetY);
        ctx.scale(scale, scale);
        const lx = 0;

        // Long hair (behind head -- drawn first)
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(lx - 18, 10, 6, 38);
        ctx.fillRect(lx + 12, 10, 6, 38);

        // Head
        ctx.fillStyle = skinColor;
        ctx.beginPath();
        ctx.arc(lx, 20, 16, 0, Math.PI * 2);
        ctx.fill();

        // Hair (top with side fringe)
        ctx.fillStyle = '#1a1a2e';
        ctx.beginPath();
        ctx.arc(lx, 16, 17, Math.PI, Math.PI * 2);
        ctx.fill();
        // Side hair strands
        ctx.fillRect(lx - 17, 16, 5, 10);
        ctx.fillRect(lx + 12, 16, 5, 10);
        // Fringe detail
        ctx.beginPath();
        ctx.moveTo(lx - 10, 5);
        ctx.quadraticCurveTo(lx - 2, 12, lx + 4, 5);
        ctx.fill();

        // Hair accessory (small bow)
        ctx.fillStyle = '#f472b6';
        ctx.beginPath();
        ctx.arc(lx + 12, 10, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ec4899';
        ctx.beginPath();
        ctx.arc(lx + 12, 10, 2, 0, Math.PI * 2);
        ctx.fill();

        // Eyes (large, expressive -- slightly larger lashes)
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(lx - 6, 20, 5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(lx + 6, 20, 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#111';
        ctx.beginPath(); ctx.arc(lx - 5, 21, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(lx + 7, 21, 2.5, 0, Math.PI * 2); ctx.fill();
        // Eyelashes
        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(lx - 11, 17); ctx.lineTo(lx - 9, 16); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(lx + 11, 17); ctx.lineTo(lx + 9, 16); ctx.stroke();

        // Mouth (smile)
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(lx, 28, 5, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();

        // Body (black tee)
        const bodyTop = 36;
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(lx - 14, bodyTop, 28, 30);

        // Shirt text 'Garage'
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 7px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Garage', lx, bodyTop + 15);

        // Arms
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(lx - 20, bodyTop + 2, 7, 18);
        ctx.fillRect(lx + 13, bodyTop + 2, 7, 18);
        ctx.fillStyle = skinColor;
        ctx.fillRect(lx - 20, bodyTop + 20, 7, 10);
        ctx.fillRect(lx + 13, bodyTop + 20, 7, 10);

        // Legs (blue jeans)
        ctx.fillStyle = '#4472C4';
        ctx.fillRect(lx - 11, bodyTop + 30, 10, 26);
        ctx.fillRect(lx + 1, bodyTop + 30, 10, 26);

        // Shoes (white sneakers)
        ctx.fillStyle = '#e5e7eb';
        ctx.fillRect(lx - 13, bodyTop + 55, 12, 6);
        ctx.fillRect(lx + 1, bodyTop + 55, 12, 6);

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
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'Engenheiro Distinto' };
        document.getElementById('hudName').textContent = player.name || '---';
        document.getElementById('hudStage').textContent = STAGE_PT[player.stage] || player.stage || 'Estagiario';
        document.getElementById('hudScore').textContent = player.score || 0;
        document.getElementById('hudErrors').textContent = (player.current_errors || 0) + ' / 3';
    },

    showChallenge(challenge) {
        State.isInChallenge = true;
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

    hideChallenge() {
        State.isInChallenge = false;
        document.getElementById('challengeOverlay').classList.remove('visible');
        SFX.resumeMusic();
    },

    showFeedback(result) {
        const fb = document.getElementById('challengeFeedback');
        const ok = result.outcome === 'correct';
        fb.innerHTML = `<div class="feedback-box ${ok ? 'correct' : 'wrong'}">
            <strong>${ok ? 'CORRETO' : 'INCORRETO'}</strong><br><br>
            ${result.explanation}
            ${!ok && result.errors_remaining !== undefined ? '<br><br>Erros restantes: ' + result.errors_remaining + ' / 3' : ''}
        </div>`;
        document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
        document.getElementById('challengeActions').style.display = 'flex';
    },

    showPromotion(stage, msg) {
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'Engenheiro Distinto' };
        document.getElementById('promotionMessage').textContent = msg;
        document.getElementById('promotionStage').textContent = STAGE_PT[stage] || stage;
        document.getElementById('promotionOverlay').style.display = 'flex';
        SFX.promote();
    },

    hidePromotion() { document.getElementById('promotionOverlay').style.display = 'none'; },

    showGameOver(stats) {
        SFX.stopMusic();
        SFX.gameOver();
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'Engenheiro Distinto' };
        document.getElementById('gameoverStats').innerHTML =
            `Cargo: ${STAGE_PT[stats.stage] || stats.stage}<br>Pontuacao: ${stats.total_score || stats.score || 0}<br>Tentativas: ${stats.total_attempts || '---'}<br>Fim de Jogo: ${stats.game_over_count || 1}`;
        UI.showScreen('screen-gameover');
    },

    showVictory(player) {
        SFX.stopMusic();
        SFX.victory();
        const STAGE_PT = { 'Intern': 'Estagiario', 'Junior': 'Junior', 'Mid': 'Pleno', 'Senior': 'Senior', 'Staff': 'Staff', 'Principal': 'Principal', 'Distinguished': 'Engenheiro Distinto' };
        document.getElementById('victoryStats').innerHTML =
            `Engenheiro: ${player.name}<br>Cargo: ${STAGE_PT[player.stage] || player.stage}<br>Pontuacao: ${player.score}<br>Desafios: ${player.completed_challenges.length}<br>Tentativas: ${player.total_attempts}`;
        UI.showScreen('screen-victory');
    },
};

// ---- game controller ----
const Game = {
    async start() {
        const name = document.getElementById('playerName').value.trim();
        if (!name) { alert('Digite seu nome.'); return; }
        const av = UI.getSelectedAvatar();
        SFX.menuConfirm();

        try {
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

            State.challenges = await API.get('/api/challenges');

            World.init(av.index);
            UI.updateHUD(State.player);
            UI.showScreen('screen-world');
        } catch (e) { alert('Erro: ' + e.message); }
    },

    async loadSession(silent = false) {
        const id = localStorage.getItem('garage_session_id');
        if (!id) { if (!silent) alert('Nenhuma sessao salva.'); return false; }
        try {
            State.player = await API.get('/api/session/' + id);
            State.sessionId = id;
            State.challenges = await API.get('/api/challenges');
            World.init(State.player.character ? State.player.character.avatar_index : 0);
            UI.updateHUD(State.player);
            UI.showScreen('screen-world');
            return true;
        } catch (e) {
            // Session no longer exists on server -- clean up and let user start fresh
            if (e.message && (e.message.includes('not found') || e.message.includes('404'))) {
                localStorage.removeItem('garage_session_id');
                UI.updateTitleButtons();
                if (!silent) alert('Sessao anterior nao encontrada. Inicie um novo jogo.');
            } else {
                if (!silent) alert('Erro ao carregar sessao: ' + e.message);
            }
            return false;
        }
    },

    async enterRegion(regionId) {
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
            UI.hideChallenge();
            if (pending.promotion && pending.promotion.new_stage) {
                UI.showPromotion(pending.promotion.new_stage, pending.promotion.promotion_message);
                if (pending.promotion.new_stage === 'Distinguished') {
                    setTimeout(() => UI.showVictory(State.player), 3000);
                    return;
                }
            }
            IDE.open(pending.npc);
            return;
        }

        if (pending && pending.type === 'next_theory') {
            State.player = await API.get('/api/session/' + State.sessionId);
            State.challenges = await API.get('/api/challenges');
            UI.updateHUD(State.player);
            UI.hideChallenge();
            if (pending.promotion && pending.promotion.new_stage) {
                UI.showPromotion(pending.promotion.new_stage, pending.promotion.promotion_message);
                if (pending.promotion.new_stage === 'Distinguished') {
                    setTimeout(() => UI.showVictory(State.player), 3000);
                    return;
                }
            }
            if (pending.region) Game.enterRegion(pending.region);
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
};

// ---- java semantic analyzer (pedagogical compiler sim) ----
const JavaAnalyzer = {

    /**
     * Remove comments and string literals for analysis,
     * preserving line structure for error reporting.
     */
    _stripCommentsAndStrings(code) {
        // Replace string contents but keep quotes for structural analysis
        let stripped = code.replace(/\/\/.*$/gm, '');
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
        // Skip chars inside strings
        for (let ln = 0; ln < lines.length; ln++) {
            let inStr = false;
            let strChar = null;
            for (let c = 0; c < lines[ln].length; c++) {
                const ch = lines[ln][c];
                if (inStr) { if (ch === strChar && lines[ln][c - 1] !== '\\') inStr = false; continue; }
                if (ch === '"' || ch === '\'') { inStr = true; strChar = ch; continue; }
                if (ch === '/' && lines[ln][c + 1] === '/') break; // line comment
                if (pairs[ch]) stack.push({ ch, line: ln + 1 });
                else if (reverse[ch]) {
                    if (stack.length === 0) return { ok: false, line: ln + 1, msg: 'Erro de compilacao: Linha ' + (ln + 1) + ': "' + ch + '" sem abertura correspondente.' };
                    const top = stack.pop();
                    if (pairs[top.ch] !== ch) return { ok: false, line: ln + 1, msg: 'Erro de compilacao: Linha ' + (ln + 1) + ': esperava "' + pairs[top.ch] + '" mas encontrou "' + ch + '". Abertura na linha ' + top.line + '.' };
                }
            }
        }
        if (stack.length > 0) {
            const top = stack[stack.length - 1];
            return { ok: false, line: top.line, msg: 'Erro de compilacao: "' + top.ch + '" aberto na linha ' + top.line + ' nunca foi fechado. Falta "' + pairs[top.ch] + '".' };
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
            if (line === '{' || line === '}' || line === '};' || line === '},' || line.endsWith('{') || line.endsWith('}')) continue;
            if (/^(public|private|protected|static|class|interface|enum|if|else|for|while|do|switch|case|default|try|catch|finally|import|package)\b/.test(line) && line.endsWith('{')) continue;
            if (/^\}/.test(line)) continue;
            if (/^(import|package)\s/.test(line) && !line.endsWith(';'))
                return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': falta ";" no final da declaracao.' };
            // Statement lines (assignments, method calls, return, declarations)
            if (/^(int|long|double|float|char|boolean|String|var|return|System|HashMap|Stack|Queue|LinkedList|ListNode|TreeNode)\b/.test(line) ||
                /^\w+\s*[\.\[\(=]/.test(line) ||
                /^\w+\s+\w+\s*=/.test(line)) {
                if (!line.endsWith(';') && !line.endsWith('{') && !line.endsWith('}') && !line.endsWith(',') && !line.endsWith('(') && !/\)\s*\{/.test(line))
                    return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': falta ";" no final da declaracao.' };
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
                /\b(HashMap|Map|Stack|Queue|LinkedList|List|ArrayList|Set|HashSet|TreeMap)\s*<[^>]*>\s+(\w+)\s*[=;]/,
                /\b(ListNode|TreeNode)\s+(\w+)\s*[=;]/,
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
            const forEachMatch = line.match(/for\s*\(\s*([\w.]+(?:<[^>]*>)?(?:\[\s*\])?)\s+(\w+)\s*:\s*[^)]+\)/);
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
                    return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': variavel do inicializador "' + initVar + '" e diferente da variavel na condicao "' + condVar + '". O for espera a mesma variavel.' };
                }

                // Check: increment must reference the same var
                if (!incrExpr.includes(initVar)) {
                    return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': incremento "' + incrExpr + '" nao usa a variavel iteradora "' + initVar + '".' };
                }

                // Check: if condition references .length, the object must be declared
                const lengthMatch = condExpr.match(/(\w+)\.length/);
                if (lengthMatch) {
                    const arrName = lengthMatch[1];
                    if (!decls.has(arrName)) {
                        return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': variavel "' + arrName + '" nao foi declarada. Voce quis dizer outra variavel?' };
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
            const printMatch = line.match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\(([^)]*)\)/);
            if (printMatch) {
                const arg = printMatch[1].trim();
                if (!arg) {
                    // Empty println() -- only valid as blank line print, but flag if inside a loop iterating an array
                    const contextAbove = lines.slice(Math.max(0, i - 5), i).join('\n');
                    if (/for\s*\(/.test(contextAbove) && decls.size > 0) {
                        // Inside or near a for loop -- empty println is likely wrong
                        return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': System.out.println() sem argumento. Voce provavelmente deveria imprimir um elemento do array. Ex: System.out.println(arr[i]);' };
                    }
                    continue;
                }
                // Check if arg references undeclared variables (basic check)
                // Extract variable references from the argument (skip strings and numbers)
                const cleanArg = arg.replace(/"[^"]*"/g, '').replace(/\b\d+\b/g, '').trim();
                if (cleanArg) {
                    const varRefs = cleanArg.match(/\b[a-zA-Z_]\w*\b/g) || [];
                    const javaKeywords = new Set(['new', 'null', 'true', 'false', 'this', 'super', 'instanceof', 'return', 'if', 'else', 'for', 'while']);
                    const javaClasses = new Set(['System', 'String', 'Integer', 'Double', 'Math', 'Arrays', 'Map', 'Entry', 'Character']);
                    const javaMethods = new Set(['toString', 'valueOf', 'parseInt', 'getKey', 'getValue', 'size', 'length', 'charAt', 'format', 'isEmpty', 'pop', 'push', 'poll', 'peek', 'get', 'containsKey', 'entrySet', 'add', 'remove']);
                    for (const ref of varRefs) {
                        if (javaKeywords.has(ref) || javaClasses.has(ref) || javaMethods.has(ref)) continue;
                        // Check method params (rough: check if method signature has this var)
                        const methodParam = code.match(new RegExp('\\(\\s*(?:int\\[\\]|int|String|long|double|boolean|float|char|String\\[\\])\\s+' + ref + '\\b'));
                        if (methodParam) continue;
                        if (!decls.has(ref)) {
                            return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': variavel "' + ref + '" nao foi declarada neste escopo.' };
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
            const m = lines[i].match(/\b(int|long|double|float|String|char)\s*\[\s*\]\s+(\w+)\s*=/);
            if (m) arrayDecls.push({ name: m[2], type: m[1], line: i + 1 });
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
                    return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': voce esta usando "' + iterName + '" como iterador do for, mas "' + iterName + '" ja e o nome do seu array (declarado na linha ' + arr.line + '). Use um nome diferente para o contador, como "i". Ex: for (int i = 0; i < ' + arr.name + '.length; i++)' };
                }
            }

            // Check condition uses a declared array for .length
            const condMatch = line.match(/(\w+)\.length/);
            if (condMatch) {
                const condArr = condMatch[1];
                const knownArr = arrayDecls.find(a => a.name === condArr);
                if (!knownArr && condArr !== 'args') {
                    // Check if they wrote the wrong name
                    if (arrayDecls.length > 0) {
                        return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': "' + condArr + '.length" -- variavel "' + condArr + '" nao existe. O array se chama "' + arrayDecls[0].name + '". Use: ' + arrayDecls[0].name + '.length' };
                    }
                    return { ok: false, line: i + 1, msg: 'Erro de compilacao: Linha ' + (i + 1) + ': "' + condArr + '" nao e uma variavel declarada.' };
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
                        return { ok: false, line: j + 1, msg: 'Erro de compilacao: Linha ' + (j + 1) + ': System.out.println() esta vazio dentro do loop. Para imprimir elementos do array, use: System.out.println(' + arrayDecls[0].name + '[' + iterName + ']);' };
                    }
                    // Check if println uses array[wrong_var]
                    const printArrMatch = lines[j].match(/System\s*\.\s*out\s*\.\s*print(?:ln)?\s*\(\s*(\w+)\s*\[\s*(\w+)\s*\]\s*\)/);
                    if (printArrMatch) {
                        const usedArr = printArrMatch[1];
                        const usedIdx = printArrMatch[2];
                        const knownArr = arrayDecls.find(a => a.name === usedArr);
                        if (!knownArr) {
                            return { ok: false, line: j + 1, msg: 'Erro de compilacao: Linha ' + (j + 1) + ': array "' + usedArr + '" nao foi declarado.' };
                        }
                        // Extract iterator declared in for-init
                        const forDeclMatch = line.match(/for\s*\(\s*int\s+(\w+)/);
                        const actualIter = forDeclMatch ? forDeclMatch[1] : iterName;
                        if (usedIdx !== actualIter) {
                            return { ok: false, line: j + 1, msg: 'Erro de compilacao: Linha ' + (j + 1) + ': indice "' + usedIdx + '" nao foi declarado neste escopo. O iterador do for e "' + actualIter + '". Use: ' + usedArr + '[' + actualIter + ']' };
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
        title: 'Hello World', concept: 'Syntax / Estrutura basica',
        language: 'java', fileName: 'HelloWorld.java',
        description: 'Escreva a classe HelloWorld com o metodo main que imprime "Hello World" no console.\n\nRegras:\n- Nome da classe: HelloWorld (CamelCase)\n- Metodo: public static void main(String[] args)\n- Saida: System.out.println("Hello World");',
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
                    if (/^hello\s*world$/i.test(typed)) return { ok: false, msg: 'Erro de compilacao: Java e case-sensitive. Use HelloWorld (H e W maiusculos).' };
                    if (typed.toLowerCase().includes('hello')) return { ok: false, msg: 'Erro de compilacao: Nome da classe incorreto: "' + typed + '". Deve ser exatamente HelloWorld.' };
                    return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar HelloWorld (CamelCase). Voce escreveu: ' + typed };
                }
                return { ok: false, msg: 'Erro de compilacao: Falta declarar a classe. Use: public class HelloWorld { ... }' };
            }
            if (!/public\s+static\s+void\s+main\s*\(\s*String\s*\[\s*\]\s+\w+\s*\)/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo main incorreto. Use: public static void main(String[] args)' };
            if (!/System\s*\.\s*out\s*\.\s*println\s*\(\s*"Hello World[!]?"\s*\)/.test(code)) {
                if (/system\s*\.\s*out/i.test(code) && !/System\.out/.test(code)) return { ok: false, msg: 'Erro de compilacao: Java e case-sensitive. Use System.out.println (S maiusculo).' };
                if (/System\s*\.\s*out\s*\.\s*print\s*\(/.test(code) && !/println/.test(code)) return { ok: false, msg: 'Erro de compilacao: Use println (com "ln" no final), nao print.' };
                if (/"hello world"/i.test(code) && !/"Hello World"/.test(code)) return { ok: false, msg: 'Erro de compilacao: O texto deve ser exatamente "Hello World" (H e W maiusculos).' };
                return { ok: false, msg: 'Erro de compilacao: Use System.out.println("Hello World");' };
            }
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Hello World\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Todo programa Java comeca com uma classe\n2. O ponto de entrada e o metodo main (assinatura fixa)\n3. System.out.println() e a funcao de saida\n\nCOLA -- Copie este codigo na IDE:\n\npublic class HelloWorld {\n    public static void main(String[] args) {\n        System.out.println("Hello World");\n    }\n}'
    },
    {
        id: 'code_var', stage: 'Intern', region: 'Apple Garage',
        title: 'Variaveis e Tipos', concept: 'Tipos primitivos / Declaracao',
        language: 'java', fileName: 'Variables.java',
        description: 'Declare e imprima:\n1. int idade = 20;\n2. double salario = 3500.50;\n3. String nome = "Dev";\n4. boolean ativo = true;\n\nImprima cada variavel com System.out.println().',
        starterCode: 'public class Variables {\n    public static void main(String[] args) {\n        // Declare suas variaveis aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Variables/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar Variables.' };
            if (!/int\s+\w+\s*=\s*\d+/.test(code)) return { ok: false, msg: 'Erro de compilacao: Declare uma variavel int. Ex: int idade = 20;' };
            if (!/double\s+\w+\s*=\s*[\d.]+/.test(code)) return { ok: false, msg: 'Erro de compilacao: Declare uma variavel double. Ex: double salario = 3500.50;' };
            if (!/String\s+\w+\s*=\s*"[^"]*"/.test(code)) return { ok: false, msg: 'Erro de compilacao: Declare uma variavel String. Ex: String nome = "Dev";' };
            if (!/boolean\s+\w+\s*=\s*(true|false)/.test(code)) return { ok: false, msg: 'Erro de compilacao: Declare uma variavel boolean. Ex: boolean ativo = true;' };
            const printCount = (code.match(/System\s*\.\s*out\s*\.\s*println/g) || []).length;
            if (printCount < 4) return { ok: false, msg: 'Erro semantico: Imprima cada variavel com System.out.println(). Faltam ' + (4 - printCount) + ' prints.' };
            // Verify println arguments reference declared vars
            const declNames = [];
            const declMatches = code.matchAll(/\b(int|double|String|boolean)\s+(\w+)\s*=/g);
            for (const m of declMatches) declNames.push(m[2]);
            const printArgs = code.matchAll(/System\s*\.\s*out\s*\.\s*println\s*\(\s*(\w+)\s*\)/g);
            for (const m of printArgs) {
                if (!declNames.includes(m[1]) && m[1] !== 'true' && m[1] !== 'false')
                    return { ok: false, msg: 'Erro de compilacao: variavel "' + m[1] + '" no println nao foi declarada.' };
            }
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 20\n> 3500.5\n> Dev\n> true\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Java tem 4 tipos basicos: int (inteiro), double (decimal), String (texto), boolean (true/false)\n2. Cada variavel precisa de tipo + nome + valor\n3. Ponto e virgula no final de cada linha\n\nCOLA -- Copie este codigo na IDE:\n\npublic class Variables {\n    public static void main(String[] args) {\n        int idade = 20;\n        double salario = 3500.50;\n        String nome = "Dev";\n        boolean ativo = true;\n\n        System.out.println(idade);\n        System.out.println(salario);\n        System.out.println(nome);\n        System.out.println(ativo);\n    }\n}'
    },
    // ── JUNIOR ──────────────────────────────────────────────────────────────
    {
        id: 'code_array', stage: 'Junior', region: 'Microsoft',
        title: 'Array e Loop', concept: 'Arrays / Iteracao',
        language: 'java', fileName: 'ArrayLoop.java',
        description: 'Crie um array de inteiros {10, 20, 30, 40, 50}.\nUse um loop for para imprimir cada elemento.\n\nDica: array.length retorna o tamanho.',
        starterCode: 'public class ArrayLoop {\n    public static void main(String[] args) {\n        // Crie o array e o loop aqui\n\n    }\n}\n',
        validator(code) {
            // Phase 1: Structural + semantic compilation
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            // Phase 2: Domain checks
            if (!/class\s+ArrayLoop/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar ArrayLoop.' };
            if (!/int\s*\[\s*\]\s+\w+\s*=\s*\{/.test(code) && !/int\s*\[\s*\]\s+\w+\s*=\s*new\s+int/.test(code))
                return { ok: false, msg: 'Erro de compilacao: Declare um array de int. Ex: int[] nums = {10, 20, 30, 40, 50};' };
            // Extract array name
            const arrMatch = code.match(/int\s*\[\s*\]\s+(\w+)\s*=/);
            const arrName = arrMatch ? arrMatch[1] : 'nums';
            // Must have a for loop
            if (!/for\s*\(/.test(code) && !/for\s*\(\s*int\s+\w+\s*:/.test(code))
                return { ok: false, msg: 'Erro de compilacao: Use um loop for para iterar o array.' };
            // Check for-each or standard for
            const forEachMatch = code.match(/for\s*\(\s*int\s+(\w+)\s*:\s*(\w+)\s*\)/);
            if (forEachMatch) {
                // For-each: verify array name matches
                if (forEachMatch[2] !== arrName)
                    return { ok: false, msg: 'Erro de compilacao: for-each itera sobre "' + forEachMatch[2] + '" mas o array se chama "' + arrName + '".' };
                // Verify println uses the loop variable
                const loopVar = forEachMatch[1];
                const printInLoop = new RegExp('System\\s*\\.\\s*out\\s*\\.\\s*println\\s*\\(\\s*' + loopVar + '\\s*\\)');
                if (!printInLoop.test(code))
                    return { ok: false, msg: 'Erro semantico: Dentro do for-each, imprima a variavel "' + loopVar + '". Ex: System.out.println(' + loopVar + ');' };
            } else {
                // Standard for: verify .length references correct array
                if (!/\.length/.test(code)) return { ok: false, msg: 'Erro semantico: Use ' + arrName + '.length como condicao do for.' };
                const lengthRef = code.match(/(\w+)\.length/);
                if (lengthRef && lengthRef[1] !== arrName && lengthRef[1] !== 'args')
                    return { ok: false, msg: 'Erro de compilacao: "' + lengthRef[1] + '.length" -- variavel "' + lengthRef[1] + '" nao existe. O array se chama "' + arrName + '". Use: ' + arrName + '.length' };
                // Verify println accesses array[i]
                const printArrAccess = new RegExp('System\\s*\\.\\s*out\\s*\\.\\s*println\\s*\\(\\s*' + arrName + '\\s*\\[\\s*\\w+\\s*\\]\\s*\\)');
                if (!printArrAccess.test(code))
                    return { ok: false, msg: 'Erro semantico: Imprima cada elemento com System.out.println(' + arrName + '[i]); dentro do loop.' };
            }
            if (!/System\s*\.\s*out\s*\.\s*println/.test(code)) return { ok: false, msg: 'Erro de compilacao: Use System.out.println() para imprimir.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 10\n> 20\n> 30\n> 40\n> 50\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Array = colecao de tamanho fixo. Indices comecam em 0.\n2. Loop for: inicializacao; condicao; incremento\n3. i < array.length garante que nao acessa fora dos limites\n\nCOLA -- Copie este codigo na IDE:\n\npublic class ArrayLoop {\n    public static void main(String[] args) {\n        int[] nums = {10, 20, 30, 40, 50};\n\n        for (int i = 0; i < nums.length; i++) {\n            System.out.println(nums[i]);\n        }\n    }\n}'
    },
    {
        id: 'code_fizzbuzz', stage: 'Junior', region: 'Nubank',
        title: 'FizzBuzz', concept: 'Condicional / Modulo',
        language: 'java', fileName: 'FizzBuzz.java',
        description: 'Implemente FizzBuzz de 1 a 15:\n- Multiplo de 3 e 5: imprima "FizzBuzz"\n- Multiplo de 3: imprima "Fizz"\n- Multiplo de 5: imprima "Buzz"\n- Caso contrario: imprima o numero\n\nPENSE ANTES: a ordem dos if/else importa!',
        starterCode: 'public class FizzBuzz {\n    public static void main(String[] args) {\n        for (int i = 1; i <= 15; i++) {\n            // Sua logica aqui\n\n        }\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+FizzBuzz/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar FizzBuzz.' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro semantico: Use um loop for.' };
            if (!/%\s*3/.test(code) || !/%\s*5/.test(code)) return { ok: false, msg: 'Erro semantico: Use o operador modulo (%). Ex: i % 3 == 0' };
            if (!/if\s*\(/.test(code)) return { ok: false, msg: 'Erro semantico: Use if/else para as condicoes.' };
            if (!/"FizzBuzz"/.test(code)) return { ok: false, msg: 'Erro semantico: Quando multiplo de 3 E 5, imprima "FizzBuzz".' };
            if (!/"Fizz"/.test(code)) return { ok: false, msg: 'Erro semantico: Quando multiplo de 3, imprima "Fizz".' };
            if (!/"Buzz"/.test(code)) return { ok: false, msg: 'Erro semantico: Quando multiplo de 5, imprima "Buzz".' };
            // Verify FizzBuzz check comes BEFORE individual Fizz/Buzz
            const fbPos = code.indexOf('FizzBuzz');
            const fPos = code.indexOf('"Fizz"');
            const bPos = code.indexOf('"Buzz"');
            if (fbPos > fPos || fbPos > bPos)
                return { ok: false, msg: 'Erro logico: A condicao "FizzBuzz" (multiplo de 3 E 5) DEVE vir ANTES das condicoes individuais "Fizz" e "Buzz". Caso contrario, 15 nunca sera FizzBuzz.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 1\n> 2\n> Fizz\n> 4\n> Buzz\n> Fizz\n> 7\n> 8\n> Fizz\n> Buzz\n> 11\n> Fizz\n> 13\n> 14\n> FizzBuzz\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. A ORDEM importa: teste "multiplo de 3 E 5" PRIMEIRO\n2. Se testar "multiplo de 3" antes, 15 imprime "Fizz" ao inves de "FizzBuzz"\n3. Operador %: a % b retorna o RESTO da divisao. Se resto == 0, e multiplo.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class FizzBuzz {\n    public static void main(String[] args) {\n        for (int i = 1; i <= 15; i++) {\n            if (i % 3 == 0 && i % 5 == 0) {\n                System.out.println("FizzBuzz");\n            } else if (i % 3 == 0) {\n                System.out.println("Fizz");\n            } else if (i % 5 == 0) {\n                System.out.println("Buzz");\n            } else {\n                System.out.println(i);\n            }\n        }\n    }\n}'
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
            if (!/import\s+java\.util\.Stack/.test(code)) return { ok: false, msg: 'Erro de compilacao: Falta import java.util.Stack;' };
            if (!/Stack\s*<\s*Integer\s*>\s+\w+\s*=\s*new\s+Stack/.test(code)) return { ok: false, msg: 'Erro de compilacao: Crie a Stack: Stack<Integer> stack = new Stack<>();' };
            if (!(/\.push\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use stack.push() para adicionar elementos.' };
            if (!(/\.pop\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use stack.pop() para remover o topo.' };
            if (!(/\.size\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use stack.size() para imprimir o tamanho.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Pop: 30\n> Tamanho: 2\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Stack = LIFO (Last In, First Out). O ultimo a entrar sai primeiro.\n2. Analogia: pilha de pratos. Voce so tira o de cima.\n3. push() coloca no topo, pop() remove do topo, peek() ve sem remover.\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.Stack;\n\npublic class StackDemo {\n    public static void main(String[] args) {\n        Stack<Integer> stack = new Stack<>();\n        stack.push(10);\n        stack.push(20);\n        stack.push(30);\n\n        int topo = stack.pop();\n        System.out.println("Pop: " + topo);\n        System.out.println("Tamanho: " + stack.size());\n    }\n}'
    },
    {
        id: 'code_linkedlist', stage: 'Mid', region: 'Facebook',
        title: 'LinkedList', concept: 'Lista encadeada / Insercao O(1)',
        language: 'java', fileName: 'LinkedListDemo.java',
        description: 'Use java.util.LinkedList para:\n1. Criar LinkedList<String>\n2. Adicionar "Alpha", "Beta", "Gamma" com add()\n3. Adicionar "First" no inicio com addFirst()\n4. Remover o ultimo com removeLast()\n5. Imprimir a lista',
        starterCode: 'import java.util.LinkedList;\n\npublic class LinkedListDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilacao: Falta import java.util.LinkedList;' };
            if (!/LinkedList\s*<\s*String\s*>\s+\w+\s*=\s*new\s+LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilacao: Crie: LinkedList<String> list = new LinkedList<>();' };
            if (!(/\.add\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use list.add() para adicionar elementos.' };
            if (!(/\.addFirst\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use list.addFirst() para inserir no inicio.' };
            if (!(/\.removeLast\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use list.removeLast() para remover o ultimo.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [First, Alpha, Beta]\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. LinkedList = nos conectados por ponteiros. Insercao no inicio/fim e O(1).\n2. Diferente de ArrayList: nao tem acesso aleatorio O(1), mas insercao/remocao nas pontas e instantanea.\n3. addFirst() insere antes do primeiro no, removeLast() remove o ultimo.\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.LinkedList;\n\npublic class LinkedListDemo {\n    public static void main(String[] args) {\n        LinkedList<String> list = new LinkedList<>();\n        list.add("Alpha");\n        list.add("Beta");\n        list.add("Gamma");\n        list.addFirst("First");\n        list.removeLast();\n        System.out.println(list);\n    }\n}'
    },
    // ── SENIOR ──────────────────────────────────────────────────────────────
    {
        id: 'code_hashmap', stage: 'Senior', region: 'Amazon',
        title: 'HashMap', concept: 'Hash table / O(1) lookup',
        language: 'java', fileName: 'HashMapDemo.java',
        description: 'Use java.util.HashMap para:\n1. Criar HashMap<String, Integer>\n2. Inserir: "Java"->1995, "Python"->1991, "Go"->2009\n3. Verificar se contem "Java" com containsKey()\n4. Obter valor de "Python" com get()\n5. Iterar com entrySet() e imprimir chave=valor',
        starterCode: 'import java.util.HashMap;\nimport java.util.Map;\n\npublic class HashMapDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.HashMap/.test(code)) return { ok: false, msg: 'Erro de compilacao: Falta import java.util.HashMap;' };
            if (!/HashMap\s*<\s*String\s*,\s*Integer\s*>/.test(code)) return { ok: false, msg: 'Erro de compilacao: Crie: HashMap<String, Integer> map = new HashMap<>();' };
            if (!(/\.put\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use map.put("key", value) para inserir.' };
            if (!(/\.containsKey\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use map.containsKey("Java") para verificar.' };
            if (!(/\.get\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use map.get("Python") para obter valor.' };
            if (!(/\.entrySet\s*\(/.test(code) || /for\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Itere com for (Map.Entry<> e : map.entrySet())' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Contem Java: true\n> Python: 1991\n> Java=1995\n> Python=1991\n> Go=2009\n\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. HashMap = tabela hash. Armazena pares chave-valor.\n2. Busca por chave e O(1) -- constante, nao importa quantos elementos.\n3. put() insere, get() busca, containsKey() verifica existencia.\n4. entrySet() retorna todos os pares para iteracao.\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.HashMap;\nimport java.util.Map;\n\npublic class HashMapDemo {\n    public static void main(String[] args) {\n        HashMap<String, Integer> map = new HashMap<>();\n        map.put("Java", 1995);\n        map.put("Python", 1991);\n        map.put("Go", 2009);\n\n        System.out.println("Contem Java: " + map.containsKey("Java"));\n        System.out.println("Python: " + map.get("Python"));\n\n        for (Map.Entry<String, Integer> e : map.entrySet()) {\n            System.out.println(e.getKey() + "=" + e.getValue());\n        }\n    }\n}'
    },
    {
        id: 'code_queue', stage: 'Senior', region: 'Mercado Livre',
        title: 'Fila (Queue)', concept: 'Estrutura FIFO / Processamento de pedidos',
        language: 'java', fileName: 'QueueDemo.java',
        description: 'Simule uma fila de pedidos do Mercado Livre:\n1. Criar Queue<String> usando LinkedList\n2. Enfileirar: "Pedido-001", "Pedido-002", "Pedido-003"\n3. Processar (poll) e imprimir cada pedido\n4. Mostrar se a fila esta vazia com isEmpty()',
        starterCode: 'import java.util.Queue;\nimport java.util.LinkedList;\n\npublic class QueueDemo {\n    public static void main(String[] args) {\n        // Implemente aqui\n\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/import\s+java\.util\.Queue/.test(code)) return { ok: false, msg: 'Erro de compilacao: Falta import java.util.Queue;' };
            if (!/Queue\s*<\s*String\s*>\s+\w+\s*=\s*new\s+LinkedList/.test(code)) return { ok: false, msg: 'Erro de compilacao: Crie: Queue<String> fila = new LinkedList<>();' };
            if (!(/\.(add|offer)\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use fila.add() ou fila.offer() para enfileirar.' };
            if (!(/\.poll\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use fila.poll() para processar o proximo da fila.' };
            if (!(/\.isEmpty\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use fila.isEmpty() para verificar se esta vazia.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> Processando: Pedido-001\n> Processando: Pedido-002\n> Processando: Pedido-003\n> Fila vazia: true\n\nFIFO: primeiro pedido a entrar e o primeiro a ser processado.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Queue = FIFO (First In, First Out). Primeiro a entrar, primeiro a sair.\n2. Analogia: fila de supermercado. Quem chegou primeiro e atendido primeiro.\n3. offer()/add() coloca no fim, poll() remove do inicio.\n4. Queue e interface, LinkedList e a implementacao.\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.Queue;\nimport java.util.LinkedList;\n\npublic class QueueDemo {\n    public static void main(String[] args) {\n        Queue<String> fila = new LinkedList<>();\n        fila.add("Pedido-001");\n        fila.add("Pedido-002");\n        fila.add("Pedido-003");\n\n        while (!fila.isEmpty()) {\n            System.out.println("Processando: " + fila.poll());\n        }\n        System.out.println("Fila vazia: " + fila.isEmpty());\n    }\n}'
    },
    {
        id: 'code_bsearch', stage: 'Senior', region: 'JP Morgan',
        title: 'Binary Search', concept: 'Busca binaria / O(log n)',
        language: 'java', fileName: 'BinarySearch.java',
        description: 'Implemente busca binaria iterativa:\n1. Metodo: static int binarySearch(int[] arr, int target)\n2. Retorna o indice do target ou -1\n3. Use while (low <= high) com mid = (low + high) / 2\n4. Teste com arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91}',
        starterCode: 'public class BinarySearch {\n    static int binarySearch(int[] arr, int target) {\n        // Implemente aqui\n        return -1;\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};\n        System.out.println(binarySearch(arr, 23));\n        System.out.println(binarySearch(arr, 99));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+BinarySearch/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar BinarySearch.' };
            if (!/static\s+int\s+binarySearch\s*\(\s*int\s*\[\s*\]\s+\w+\s*,\s*int\s+\w+\s*\)/.test(code))
                return { ok: false, msg: 'Erro de compilacao: Assinatura: static int binarySearch(int[] arr, int target)' };
            if (!/while\s*\(/.test(code)) return { ok: false, msg: 'Erro semantico: Use while (low <= high) para o loop de busca.' };
            if (!/mid/.test(code)) return { ok: false, msg: 'Erro semantico: Calcule int mid = (low + high) / 2;' };
            if (!/return\s+-?\s*1/.test(code) && !/return\s+\w+/.test(code)) return { ok: false, msg: 'Erro semantico: Retorne -1 quando nao encontrar.' };
            if (!/low/.test(code) || !/high/.test(code)) return { ok: false, msg: 'Erro semantico: Use variaveis low e high para os limites.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 5\n> -1\n\nComplexidade: O(log n) -- 20 comparacoes para 1 milhao de elementos.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Busca binaria so funciona em arrays ORDENADOS.\n2. Estrategia: dividir e conquistar. Olhe o meio. Se alvo < meio, descarte metade direita. Se alvo > meio, descarte metade esquerda.\n3. A cada passo, o espaco de busca cai pela METADE. log2(1.000.000) = ~20 passos.\n4. Variaveis: low (inicio), high (fim), mid (meio).\n\nCOLA -- Copie este codigo na IDE:\n\npublic class BinarySearch {\n    static int binarySearch(int[] arr, int target) {\n        int low = 0, high = arr.length - 1;\n        while (low <= high) {\n            int mid = (low + high) / 2;\n            if (arr[mid] == target) return mid;\n            else if (arr[mid] < target) low = mid + 1;\n            else high = mid - 1;\n        }\n        return -1;\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};\n        System.out.println(binarySearch(arr, 23));\n        System.out.println(binarySearch(arr, 99));\n    }\n}'
    },
    // ── STAFF ───────────────────────────────────────────────────────────────
    {
        id: 'code_twosum', stage: 'Staff', region: 'Tesla / SpaceX',
        title: 'Two Sum (HashMap)', concept: 'Hash lookup O(n) / Otimizacao',
        language: 'java', fileName: 'TwoSum.java',
        description: 'Implemente Two Sum com HashMap:\n1. Metodo: static int[] twoSum(int[] nums, int target)\n2. Retorna indices dos dois numeros que somam target\n3. Use HashMap para lookup O(1)\n4. Complexidade total: O(n)\n5. Teste: nums={2,7,11,15}, target=9 -> [0,1]',
        starterCode: 'import java.util.HashMap;\nimport java.util.Arrays;\n\npublic class TwoSum {\n    static int[] twoSum(int[] nums, int target) {\n        // Implemente aqui\n        return new int[]{};\n    }\n\n    public static void main(String[] args) {\n        int[] result = twoSum(new int[]{2, 7, 11, 15}, 9);\n        System.out.println(Arrays.toString(result));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+TwoSum/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar TwoSum.' };
            if (!/HashMap/.test(code)) return { ok: false, msg: 'Erro semantico: Use HashMap para obter complexidade O(n).' };
            if (!(/\.put\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use map.put() para armazenar valores vistos.' };
            if (!(/\.containsKey\s*\(/.test(code) || /\.get\s*\(/.test(code))) return { ok: false, msg: 'Erro semantico: Use map.containsKey() ou map.get() para verificar o complemento.' };
            if (!/target\s*-/.test(code) && !/\-\s*\w+\[/.test(code)) return { ok: false, msg: 'Erro semantico: O complemento e target - nums[i]. Verifique se ja existe no mapa.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [0, 1]\n\nComplexidade: O(n) -- uma unica passada com HashMap.\nBrute force seria O(n^2). Voce otimizou.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Forca bruta: testar todos os pares = O(n^2). Muito lento.\n2. Insight: para cada numero X, o "par" dele e (target - X). Se esse par ja apareceu, achamos!\n3. HashMap armazena numeros ja vistos. Para cada novo numero, olhamos se o complemento ja esta la.\n4. Uma unica passagem pelo array = O(n).\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.HashMap;\nimport java.util.Arrays;\n\npublic class TwoSum {\n    static int[] twoSum(int[] nums, int target) {\n        HashMap<Integer, Integer> map = new HashMap<>();\n        for (int i = 0; i < nums.length; i++) {\n            int comp = target - nums[i];\n            if (map.containsKey(comp)) {\n                return new int[]{map.get(comp), i};\n            }\n            map.put(nums[i], i);\n        }\n        return new int[]{};\n    }\n\n    public static void main(String[] args) {\n        int[] result = twoSum(new int[]{2, 7, 11, 15}, 9);\n        System.out.println(Arrays.toString(result));\n    }\n}'
    },
    {
        id: 'code_fibonacci', stage: 'Staff', region: 'Itau',
        title: 'Fibonacci Iterativo', concept: 'Recursao vs Iteracao / Eficiencia',
        language: 'java', fileName: 'Fibonacci.java',
        description: 'Implemente Fibonacci ITERATIVO (nao recursivo):\n1. Metodo: static long fibonacci(int n)\n2. fibonacci(0)=0, fibonacci(1)=1\n3. fibonacci(n) = fibonacci(n-1) + fibonacci(n-2)\n4. Use loop, NAO recursao (seria O(2^n))\n5. Teste: fibonacci(10) = 55, fibonacci(20) = 6765',
        starterCode: 'public class Fibonacci {\n    static long fibonacci(int n) {\n        // Implemente aqui (iterativo!)\n        return 0;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(fibonacci(10));\n        System.out.println(fibonacci(20));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Fibonacci/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar Fibonacci.' };
            if (!/static\s+long\s+fibonacci/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo: static long fibonacci(int n)' };
            if (/fibonacci\s*\(\s*n\s*-\s*1\s*\)/.test(code)) return { ok: false, msg: 'Erro semantico: Nao use recursao! Fibonacci recursivo e O(2^n). Use um loop for com variaveis prev e curr.' };
            if (!/for\s*\(/.test(code) && !/while\s*\(/.test(code)) return { ok: false, msg: 'Erro semantico: Use um loop for ou while. A solucao deve ser iterativa O(n).' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 55\n> 6765\n\nComplexidade: O(n) iterativo.\nRecursivo seria O(2^n) = fibonacci(50) levaria HORAS.\nIterativo calcula fibonacci(50) em microssegundos.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Fibonacci recursivo: fib(n) chama fib(n-1) e fib(n-2). Cada um chama mais dois. Explosao exponencial O(2^n).\n2. Insight: nao precisamos recalcular valores antigos. Basta guardar os dois ultimos.\n3. Variaveis: prev = f(n-2), curr = f(n-1). A cada passo: next = prev + curr.\n4. Avance: prev = curr, curr = next. Repita n vezes. O(n) tempo, O(1) espaco.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class Fibonacci {\n    static long fibonacci(int n) {\n        if (n <= 1) return n;\n        long prev = 0, curr = 1;\n        for (int i = 2; i <= n; i++) {\n            long next = prev + curr;\n            prev = curr;\n            curr = next;\n        }\n        return curr;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(fibonacci(10));\n        System.out.println(fibonacci(20));\n    }\n}'
    },
    {
        id: 'code_sort', stage: 'Staff', region: 'Uber',
        title: 'Bubble Sort', concept: 'Ordenacao / Comparacao e troca',
        language: 'java', fileName: 'BubbleSort.java',
        description: 'Implemente Bubble Sort:\n1. Metodo: static void bubbleSort(int[] arr)\n2. Compare elementos adjacentes e troque se fora de ordem\n3. Repita ate nao haver mais trocas\n4. Imprima o array ordenado\n5. Teste: {64, 34, 25, 12, 22, 11, 90}',
        starterCode: 'import java.util.Arrays;\n\npublic class BubbleSort {\n    static void bubbleSort(int[] arr) {\n        // Implemente aqui\n\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {64, 34, 25, 12, 22, 11, 90};\n        bubbleSort(arr);\n        System.out.println(Arrays.toString(arr));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+BubbleSort/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar BubbleSort.' };
            if (!/static\s+void\s+bubbleSort/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo: static void bubbleSort(int[] arr)' };
            if (!/for\s*\(/.test(code)) return { ok: false, msg: 'Erro semantico: Use dois loops for aninhados.' };
            if (!/temp/.test(code) && !/\[\s*\w+\s*\]\s*=/.test(code)) return { ok: false, msg: 'Erro semantico: Para trocar, use uma variavel temporaria: int temp = arr[j]; arr[j] = arr[j+1]; arr[j+1] = temp;' };
            if (!/\w+\s*>\s*\w+/.test(code) && !/\w+\s*<\s*\w+/.test(code)) return { ok: false, msg: 'Erro semantico: Compare elementos adjacentes: if (arr[j] > arr[j+1])' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> [11, 12, 22, 25, 34, 64, 90]\n\nBubble Sort: O(n^2). Simples mas ineficiente para grandes datasets.\nEm producao, use Arrays.sort() que e O(n log n).\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Bubble Sort "borbulha" o maior elemento para o final a cada passagem.\n2. Loop externo: n-1 passagens. Loop interno: compara vizinhos.\n3. Se arr[j] > arr[j+1], troca-os usando variavel temporaria.\n4. Otimizacao: se nenhuma troca em uma passagem, array ja esta ordenado.\n5. Complexidade: O(n^2) -- nao use em producao, mas e essencial entender.\n\nCOLA -- Copie este codigo na IDE:\n\nimport java.util.Arrays;\n\npublic class BubbleSort {\n    static void bubbleSort(int[] arr) {\n        int n = arr.length;\n        for (int i = 0; i < n - 1; i++) {\n            for (int j = 0; j < n - i - 1; j++) {\n                if (arr[j] > arr[j + 1]) {\n                    int temp = arr[j];\n                    arr[j] = arr[j + 1];\n                    arr[j + 1] = temp;\n                }\n            }\n        }\n    }\n\n    public static void main(String[] args) {\n        int[] arr = {64, 34, 25, 12, 22, 11, 90};\n        bubbleSort(arr);\n        System.out.println(Arrays.toString(arr));\n    }\n}'
    },
    // ── PRINCIPAL ───────────────────────────────────────────────────────────
    {
        id: 'code_palindrome', stage: 'Principal', region: 'Santander',
        title: 'Verificar Palindromo', concept: 'Dois ponteiros / String manipulation',
        language: 'java', fileName: 'Palindrome.java',
        description: 'Implemente verificacao de palindromo:\n1. Metodo: static boolean isPalindrome(String s)\n2. Ignore maiusculas/minusculas e caracteres nao-alfanumericos\n3. Use dois ponteiros (inicio e fim)\n4. Teste: "A man, a plan, a canal: Panama" -> true\n5. Teste: "race a car" -> false',
        starterCode: 'public class Palindrome {\n    static boolean isPalindrome(String s) {\n        // Implemente aqui\n        return false;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isPalindrome("A man, a plan, a canal: Panama"));\n        System.out.println(isPalindrome("race a car"));\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+Palindrome/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar Palindrome.' };
            if (!/static\s+boolean\s+isPalindrome/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo: static boolean isPalindrome(String s)' };
            if (!/toLowerCase/.test(code) && !/toUpperCase/.test(code)) return { ok: false, msg: 'Erro semantico: Converta para minusculas com s.toLowerCase() para ignorar case.' };
            if (!/Character\s*\.\s*isLetterOrDigit/.test(code) && !/replaceAll/.test(code) && !/isAlphanumeric/.test(code))
                return { ok: false, msg: 'Erro semantico: Filtre caracteres nao-alfanumericos com Character.isLetterOrDigit() ou replaceAll("[^a-zA-Z0-9]", "")' };
            if (!/while/.test(code) && !/for/.test(code)) return { ok: false, msg: 'Erro semantico: Use um loop com dois ponteiros (left e right).' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> true\n> false\n\nTecnica: Two Pointers. Complexidade O(n), espaco O(1).\nEssencial em entrevistas de Big Tech.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Palindromo = le igual de tras para frente.\n2. Primeiro, limpe a string: remova tudo que nao e letra/digito, converta para minusculas.\n3. Dois ponteiros: left no inicio, right no fim.\n4. Compare s[left] com s[right]. Se diferentes, nao e palindromo.\n5. Se left >= right, ja comparou tudo. E palindromo.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class Palindrome {\n    static boolean isPalindrome(String s) {\n        String clean = s.toLowerCase().replaceAll("[^a-z0-9]", "");\n        int left = 0, right = clean.length() - 1;\n        while (left < right) {\n            if (clean.charAt(left) != clean.charAt(right)) return false;\n            left++;\n            right--;\n        }\n        return true;\n    }\n\n    public static void main(String[] args) {\n        System.out.println(isPalindrome("A man, a plan, a canal: Panama"));\n        System.out.println(isPalindrome("race a car"));\n    }\n}'
    },
    {
        id: 'code_reverse', stage: 'Principal', region: 'Bradesco',
        title: 'Reverter Lista In-Place', concept: 'Manipulacao de ponteiros / In-place',
        language: 'java', fileName: 'ReverseList.java',
        description: 'Implemente reversao de lista encadeada:\n1. Classe ListNode com int val e ListNode next\n2. Metodo: static ListNode reverseList(ListNode head)\n3. Reverta in-place (sem criar nova lista)\n4. Use 3 ponteiros: prev, curr, next\n5. Complexidade: O(n) tempo, O(1) espaco',
        starterCode: 'public class ReverseList {\n    static class ListNode {\n        int val;\n        ListNode next;\n        ListNode(int v) { val = v; }\n    }\n\n    static ListNode reverseList(ListNode head) {\n        // Implemente aqui\n        return head;\n    }\n\n    public static void main(String[] args) {\n        ListNode head = new ListNode(1);\n        head.next = new ListNode(2);\n        head.next.next = new ListNode(3);\n        head.next.next.next = new ListNode(4);\n\n        ListNode rev = reverseList(head);\n        while (rev != null) {\n            System.out.print(rev.val + " ");\n            rev = rev.next;\n        }\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+ReverseList/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar ReverseList.' };
            if (!/class\s+ListNode/.test(code)) return { ok: false, msg: 'Erro de compilacao: Defina a classe ListNode com val e next.' };
            if (!/static\s+ListNode\s+reverseList/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo: static ListNode reverseList(ListNode head)' };
            if (!/prev/.test(code)) return { ok: false, msg: 'Erro semantico: Use um ponteiro prev (inicializado como null) para rastrear o no anterior.' };
            if (!/while/.test(code)) return { ok: false, msg: 'Erro semantico: Use while (curr != null) para percorrer a lista.' };
            if (!/\.next/.test(code)) return { ok: false, msg: 'Erro semantico: Manipule os ponteiros .next para inverter as conexoes.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 4 3 2 1\n\nLista revertida in-place. O(n) tempo, O(1) espaco.\nClassico de entrevistas: nao crie nova lista, apenas inverta ponteiros.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Lista encadeada: cada no aponta para o proximo. Para reverter, cada no deve apontar para o ANTERIOR.\n2. Tres ponteiros: prev (onde vou apontar), curr (no atual), next (salvar referencia antes de perder).\n3. A cada passo: salve next = curr.next, inverta curr.next = prev, avance prev = curr, curr = next.\n4. Quando curr == null, prev e a nova cabeca.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class ReverseList {\n    static class ListNode {\n        int val;\n        ListNode next;\n        ListNode(int v) { val = v; }\n    }\n\n    static ListNode reverseList(ListNode head) {\n        ListNode prev = null;\n        ListNode curr = head;\n        while (curr != null) {\n            ListNode next = curr.next;\n            curr.next = prev;\n            prev = curr;\n            curr = next;\n        }\n        return prev;\n    }\n\n    public static void main(String[] args) {\n        ListNode head = new ListNode(1);\n        head.next = new ListNode(2);\n        head.next.next = new ListNode(3);\n        head.next.next.next = new ListNode(4);\n\n        ListNode rev = reverseList(head);\n        while (rev != null) {\n            System.out.print(rev.val + " ");\n            rev = rev.next;\n        }\n    }\n}'
    },
    {
        id: 'code_tree', stage: 'Principal', region: 'Cloud Valley',
        title: 'Inverter Arvore Binaria', concept: 'Recursao / Arvore binaria',
        language: 'java', fileName: 'InvertTree.java',
        description: 'Implemente a inversao de arvore binaria:\n1. Classe TreeNode com int val, TreeNode left, right\n2. Metodo: static TreeNode invertTree(TreeNode root)\n3. Troca left <-> right recursivamente\n4. Retorna a raiz invertida\n5. Complexidade: O(n)',
        starterCode: 'public class InvertTree {\n    static class TreeNode {\n        int val;\n        TreeNode left, right;\n        TreeNode(int v) { val = v; }\n    }\n\n    static TreeNode invertTree(TreeNode root) {\n        // Implemente aqui\n        return root;\n    }\n\n    public static void main(String[] args) {\n        TreeNode root = new TreeNode(4);\n        root.left = new TreeNode(2);\n        root.right = new TreeNode(7);\n        root.left.left = new TreeNode(1);\n        root.left.right = new TreeNode(3);\n\n        TreeNode inv = invertTree(root);\n        System.out.println(inv.left.val);  // 7\n        System.out.println(inv.right.val); // 2\n    }\n}\n',
        validator(code) {
            const compile = JavaAnalyzer.analyze(code);
            if (!compile.ok) return compile;
            if (!/class\s+InvertTree/.test(code)) return { ok: false, msg: 'Erro de compilacao: A classe deve se chamar InvertTree.' };
            if (!/class\s+TreeNode/.test(code)) return { ok: false, msg: 'Erro de compilacao: Defina a classe interna TreeNode com val, left, right.' };
            if (!/static\s+TreeNode\s+invertTree/.test(code)) return { ok: false, msg: 'Erro de compilacao: Metodo: static TreeNode invertTree(TreeNode root)' };
            if (!/invertTree\s*\(\s*root\s*\.\s*left\s*\)/.test(code) && !/invertTree\s*\(\s*\w+\s*\.\s*left\s*\)/.test(code) &&
                !/invertTree\s*\(\s*root\s*\.\s*right\s*\)/.test(code) && !/invertTree\s*\(\s*\w+\s*\.\s*right\s*\)/.test(code))
                return { ok: false, msg: 'Erro semantico: Use recursao: invertTree(root.left) e invertTree(root.right).' };
            if (!/null/.test(code)) return { ok: false, msg: 'Erro semantico: Caso base: if (root == null) return null;' };
            const swapPattern = /(temp|TreeNode\s+\w+)\s*=\s*root\.\s*(left|right)/;
            const directSwap = /root\.\s*left\s*=.*root\.\s*right|root\.\s*right\s*=.*root\.\s*left/;
            if (!swapPattern.test(code) && !directSwap.test(code)) return { ok: false, msg: 'Erro semantico: Troque left e right. Use variavel temporaria ou troca direta.' };
            return { ok: true, msg: 'BUILD SUCCESSFUL\n> 7\n> 2\n\nArvore invertida com sucesso. Complexidade O(n).\nEsta e uma questao classica de entrevistas BigTech.\nProcesso finalizado com codigo de saida 0.' };
        },
        helpText: 'COMO PENSAR:\n1. Arvore binaria: cada no tem 0, 1 ou 2 filhos (left e right).\n2. Inverter = espelhar. O que estava na esquerda vai para a direita e vice-versa.\n3. Recursao: para cada no, troque left e right. Depois, inverta a subarvore esquerda e a direita.\n4. Caso base: se o no e null, retorne null (arvore vazia).\n5. Use uma variavel temporaria para a troca.\n\nCOLA -- Copie este codigo na IDE:\n\npublic class InvertTree {\n    static class TreeNode {\n        int val;\n        TreeNode left, right;\n        TreeNode(int v) { val = v; }\n    }\n\n    static TreeNode invertTree(TreeNode root) {\n        if (root == null) return null;\n        TreeNode temp = root.left;\n        root.left = invertTree(root.right);\n        root.right = invertTree(temp);\n        return root;\n    }\n\n    public static void main(String[] args) {\n        TreeNode root = new TreeNode(4);\n        root.left = new TreeNode(2);\n        root.right = new TreeNode(7);\n        root.left.left = new TreeNode(1);\n        root.left.right = new TreeNode(3);\n\n        TreeNode inv = invertTree(root);\n        System.out.println(inv.left.val);\n        System.out.println(inv.right.val);\n    }\n}'
    },
];

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

    /**
     * Opens the IDE overlay with a coding challenge appropriate for the player stage.
     * Called after the theory challenge is answered correctly.
     */
    open(npc) {
        const stage = State.player ? State.player.stage : 'Intern';
        const region = npc ? npc.region : null;
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

        this._currentChallenge = challenge;
        this._currentNpc = npc || null;
        this._attempts = 0;
        this._solved = false;

        // Populate UI
        document.getElementById('ideFileName').textContent = challenge.fileName;
        const IDE_STAGE_PT = { 'Intern': 'ESTAGIARIO', 'Junior': 'JUNIOR', 'Mid': 'PLENO', 'Senior': 'SENIOR', 'Staff': 'STAFF', 'Principal': 'PRINCIPAL', 'Distinguished': 'ENGENHEIRO DISTINTO' };
        document.getElementById('ideStage').textContent = IDE_STAGE_PT[stage] || stage.toUpperCase();
        document.getElementById('ideSideFileName').textContent = challenge.fileName;
        document.getElementById('ideChallengeTitle').textContent = challenge.title;
        document.getElementById('ideChallengeDesc').textContent = challenge.description;
        document.getElementById('ideConceptTag').textContent = challenge.concept;
        document.getElementById('ideCodeInput').value = challenge.starterCode || '';
        document.getElementById('ideCodeInput').placeholder = '// Escreva seu codigo ' + challenge.language.toUpperCase() + ' aqui...';
        document.getElementById('ideSkipBtn').style.display = 'none';

        // Reset CONTINUAR button and restore original buttons
        const continueBtn = document.getElementById('ideContinueBtn');
        if (continueBtn) continueBtn.style.display = 'none';
        document.getElementById('ideRunBtn').style.display = 'flex';
        document.getElementById('ideHelpBtn').style.display = 'flex';

        // Terminal reset
        document.getElementById('ideTermOutput').innerHTML = '<span class="ide-prompt">&gt;</span> Aguardando codigo...\n<span class="ide-term-info">Desafio: ' + challenge.title + '</span>\n<span class="ide-term-info">Conceito: ' + challenge.concept + '</span>';
        const termStatus = document.getElementById('ideTermStatus');
        termStatus.textContent = 'Pronto';
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
            term.innerHTML += '\n<span class="ide-term-error">ERRO: Editor vazio. Escreva seu codigo.</span>';
            return;
        }

        // Compile check
        term.innerHTML += '\n<span class="ide-prompt">&gt;</span> javac ' + ch.fileName + '\n';

        const result = ch.validator(code);

        if (result.ok) {
            term.innerHTML += '<span class="ide-term-success">Compilation successful.</span>\n';
            term.innerHTML += '<span class="ide-prompt">&gt;</span> java ' + ch.fileName.replace('.java', '') + '\n';
            term.innerHTML += '<span class="ide-term-success">' + result.msg + '</span>';
            term.innerHTML += '\n\n<span class="ide-term-success">DESAFIO COMPLETO! Codigo validado com sucesso.</span>';
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

        document.getElementById('ideHelpMentor').textContent = ch.helpMentor;
        document.getElementById('ideHelpContent').textContent = ch.helpText;
        document.getElementById('ideHelpOverlay').style.display = 'flex';
    },

    closeHelp() {
        document.getElementById('ideHelpOverlay').style.display = 'none';
        document.getElementById('ideCodeInput').focus();
    },

    skip() {
        const term = document.getElementById('ideTermOutput');
        term.innerHTML += '\n<span class="ide-term-warn">Desafio pulado. Estude o conceito para a proxima vez.</span>';

        // Show the correct answer in terminal as learning opportunity
        if (this._currentChallenge && this._currentChallenge.helpText) {
            term.innerHTML += '\n<span class="ide-term-info">--- SOLUCAO DE REFERENCIA ---</span>';
            term.innerHTML += '\n<span class="ide-term-info">' + this._currentChallenge.helpText + '</span>';
        }

        if (State.lockedRegion) {
            term.innerHTML += '\n<span class="ide-term-warn">Voce continua dentro da empresa. Interaja com o fundador para tentar novamente.</span>';
        }

        // Do NOT mark _solved so IDE.close will not unlock
        setTimeout(() => this.close(), 3000);
    },

    close() {
        document.getElementById('ideOverlay').classList.remove('visible');
        document.getElementById('ideHelpOverlay').style.display = 'none';
        const wasSolved = this._solved;
        const regionBeingWorked = State.lockedRegion;
        this._currentChallenge = null;
        this._currentNpc = null;
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
                State.companyComplete = true;
                World.showDialog('SISTEMA', regionBeingWorked,
                    'Parabens! Voce completou TODOS os desafios em ' + regionBeingWorked + '. Voce esta livre para explorar e coletar livros.');
                // Clear completion flag after dialog
                setTimeout(() => { State.companyComplete = false; }, 3000);
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
                    throw new Error('As senhas nao coincidem.');
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
        if (Auth.hasSession()) {
            // Auto-resume: refresh must return to where the player was
            const resumed = await Game.loadSession(true);
            if (!resumed) {
                UI.showScreen('screen-title');
                UI.updateTitleButtons();
            }
        } else {
            UI.showScreen('screen-title');
            UI.updateTitleButtons();
        }
    } else {
        UI.showScreen('screen-login');
    }
});
