// GAME ENGINE - DOMINUS FX 2D
// Monolithic Frontend Logic

const Game = {
    state: {
        role: "Intern",
        xp: 0,
        level: 1,
        completed_challenges: []
    },
    challenges: [],
    
    // Config
    roles: ["Intern", "Junior", "Pleno", "Senior", "Principal"],
    
    // Asset Configuration (Decoupled Visuals)
    assets: {
        "Intern": "/static/assets/char_intern.png",
        "Junior": "/static/assets/char_junior.png",
        "Pleno": "/static/assets/char_pleno.png",
        "Senior": "/static/assets/char_senior.png",
        "Principal": "/static/assets/char_principal.png",
        "Default": "/static/assets/char_default.png"
    },

    getSprite: (role) => {
        // Engineering Decision: Robust Fallback
        // usage of optional chaining for safety
        return Game.assets[role] ?? Game.assets["Default"];
    },

    init: async () => {
        console.log("Initializing Silicon Valley Engine...");
        await Game.loadData();
        Render.scene();
        Render.ui();
    },

    loadData: async () => {
        try {
            const res = await fetch('/api/challenges');
            Game.challenges = await res.json();
            // Load save if exists
            const save = localStorage.getItem('dominus_save');
            if(save) Game.state = JSON.parse(save);
        } catch(e) {
            console.error("Failed to load game data", e);
        }
    },

    save: () => {
        localStorage.setItem('dominus_save', JSON.stringify(Game.state));
        Render.ui();
    },

    getChallengesByRole: (role) => {
        return Game.challenges.filter(c => c.role === role && !Game.state.completed_challenges.includes(c.id));
    },

    handleInteraction: (npcRole) => {
        const available = Game.getChallengesByRole(npcRole);
        
        // Progression Lock
        if(Game.roles.indexOf(npcRole) > Game.roles.indexOf(Game.state.role) + 1) {
            alert(`Você ainda é ${Game.state.role}. Ganhe experiência para falar com o ${npcRole}.`);
            return;
        }

        if(available.length === 0) {
            alert(`Todos os desafios de nível ${npcRole} completados!`);
            return;
        }

        // Pick next challenge
        const challenge = available[0];
        UI.showChallenge(challenge);
    },

    submitAnswer: (challenge, index) => {
        const isCorrect = index === challenge.correct_index;
        const feedback = isCorrect ? challenge.explanation : challenge.wrong_explanation;
        
        UI.showFeedback(isCorrect, feedback, () => {
            if(isCorrect) {
                Game.state.xp += 100;
                Game.state.completed_challenges.push(challenge.id);
                Game.checkLevelUp();
                Game.save();
            }
            UI.closeModal();
        });
    },

    checkLevelUp: () => {
        // Simple logic: 2 challenges per level to promote
        const currentRoleIdx = Game.roles.indexOf(Game.state.role);
        const challengesDoneInRole = Game.state.completed_challenges.filter(id => id.includes(Game.state.role.toLowerCase())).length;
        
        if(challengesDoneInRole >= 2 && currentRoleIdx < Game.roles.length - 1) {
            Game.state.role = Game.roles[currentRoleIdx + 1];
            alert(`PROMOÇÃO! Você agora é ${Game.state.role}!`);
        }
    }
};

const Render = {
    scene: () => {
        const container = document.getElementById('npc-container');
        container.innerHTML = '';
        
        // Define NPCs positions (Mapped to "Apple Park" / Campus Layout)
        // Creating a journey from the outskirts to the inner circle
        const npcs = [
            { role: "Intern", x: 10, y: 70, name: "Estagiário (Gate)" },      // Entrance
            { role: "Junior", x: 25, y: 60, name: "Dev Junior (Lobby)" },     // Walking in
            { role: "Pleno", x: 45, y: 55, name: "Eng. Pleno (Labs)" },       // The work area
            { role: "Senior", x: 65, y: 60, name: "Tech Lead (Garden)" },     // Relaxed/Mentoring
            { role: "Principal", x: 80, y: 70, name: "Principal (Theater)" }  // The goal
        ];

        npcs.forEach(npc => {
            const el = document.createElement('div');
            el.className = `character role-${npc.role}`;
            // Use Top/Left for 2D positioning map
            el.style.left = `${npc.x}%`;
            el.style.top = `${npc.y}%`; 
            
            // Decoupled Sprite Loading
            const spriteUrl = Game.getSprite(npc.role);
            
            el.innerHTML = `
                <div class="char-sprite" style="background-image: url('${spriteUrl}');">
                    <!-- CSS Fallback applied via class if image fails to load (404 handled by browser engine) -->
                </div>
                <div class="char-name">${npc.name}</div>
                <div class="char-role">${npc.role}</div>
            `;
            el.onclick = () => Game.handleInteraction(npc.role);
            container.appendChild(el);
        });
    },

    ui: () => {
        document.getElementById('stat-role').innerText = Game.state.role;
        document.getElementById('stat-xp').innerText = `${Game.state.xp} XP`;
    }
};

const UI = {
    modal: document.getElementById('challenge-modal'),
    
    showChallenge: (c) => {
        const body = document.getElementById('m-body');
        const title = document.getElementById('m-title');
        const opts = document.getElementById('m-options');
        const feedback = document.getElementById('m-feedback');
        
        title.innerText = `[${c.role}] ${c.title}`;
        body.innerText = c.question;
        feedback.style.display = 'none';
        opts.innerHTML = '';

        c.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'btn-option';
            btn.innerText = opt;
            btn.onclick = () => {
                // Visual selection state
                Array.from(opts.children).forEach(b => b.disabled = true);
                if(idx === c.correct_index) btn.classList.add('correct');
                else btn.classList.add('wrong');
                
                Game.submitAnswer(c, idx);
            };
            opts.appendChild(btn);
        });

        UI.modal.classList.add('visible');
    },

    showFeedback: (success, text, callback) => {
        const area = document.getElementById('m-feedback');
        const content = document.getElementById('m-feedback-text');
        const btn = document.getElementById('m-next-btn');
        
        area.style.display = 'block';
        content.innerHTML = (success ? "✅ <b>CORRETO:</b> " : "❌ <b>INCORRETO:</b> ") + text;
        
        btn.onclick = callback;
    },

    closeModal: () => {
        UI.modal.classList.remove('visible');
        Render.ui();
    }
};

// Boot
window.onload = Game.init;