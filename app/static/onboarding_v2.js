document.addEventListener('DOMContentLoaded', () => {
    let pendingReviews = [];
    let currentCardIndex = 0;
    let comboCount = 0;
    let evaluatedItems = [];

    // Confetti logic
    const canvas = document.getElementById('confetti-canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    let particles = [];

    function fireConfetti(x, y) {
        const colors = ['#f44336', '#4caf50', '#3b82f6', '#facc15', '#8bc34a'];
        for (let i = 0; i < 30; i++) {
            particles.push({
                x: x,
                y: y,
                r: Math.random() * 4 + 2,
                dx: Math.random() * 6 - 3,
                dy: Math.random() * -6 - 2,
                color: colors[Math.floor(Math.random() * colors.length)],
                life: 1.0
            });
        }
    }

    function animateConfetti() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < particles.length; i++) {
            let p = particles[i];
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = p.color + Math.floor(p.life * 255).toString(16).padStart(2, '0');
            ctx.fill();
            p.x += p.dx;
            p.y += p.dy;
            p.dy += 0.1; // gravity
            p.life -= 0.02;
        }
        particles = particles.filter(p => p.life > 0);
        requestAnimationFrame(animateConfetti);
    }
    animateConfetti();

    // Resize canvas
    window.addEventListener('resize', () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    });

    async function fetchPendingReviews() {
        if (window.APP_CONFIG && window.APP_CONFIG.isTest) {
            pendingReviews = [
                { disciplina: 'CÁLCULO I', professor: 'ISAAC NEWTON' },
                { disciplina: 'FÍSICA GERAL', professor: 'ALBERT EINSTEIN' },
                { disciplina: 'ESTRUTURAS DE DADOS', professor: 'ALAN TURING' }
            ];
        } else {
            try {
                const res = await fetch('/api/avaliacoes/pendentes');
                if (res.ok) {
                    const data = await res.json();
                    pendingReviews = data.pendentes || [];
                }
            } catch(e) {}
        }
    }

    // Fase 1: Loading
    async function startLoadingPhase() {
        const CIRC = 264;
        const ringFg = document.getElementById('ring-fg');
        const ringPct = document.getElementById('ring-pct');
        const statusText = document.getElementById('status-text');

        function setProgress(pct, text) {
            ringFg.style.strokeDashoffset = CIRC - (CIRC * pct / 100);
            ringPct.textContent = Math.floor(pct) + '%';
            if (pct >= 100) ringFg.style.stroke = '#10b981';
            if (text) {
                statusText.classList.add('swap');
                setTimeout(() => {
                    statusText.textContent = text;
                    statusText.classList.remove('swap');
                }, 200);
            }
        }

        setProgress(0, "Conectando ao SIGAA...");

        try {
            let progress = 10;
            setProgress(progress, "Iniciando sincronização...");
            
            const simInterval = setInterval(() => {
                if (progress < 85) {
                    progress += Math.random() * 8;
                    setProgress(progress, "Recuperando histórico completo...");
                }
            }, 300);

            if (window.APP_CONFIG && !window.APP_CONFIG.isTest) {
                await fetch('/api/academic_profile');
            } else {
                await new Promise(r => setTimeout(r, 2000));
            }
            
            clearInterval(simInterval);
            setProgress(100, "Tudo pronto!");
        } catch(e) {
            console.error("Fetch error", e);
            setProgress(100, "Finalizado");
        }

        // Aguarda 500ms para a animação do 100% terminar
        await new Promise(r => setTimeout(r, 500));

        await fetchPendingReviews();

        document.getElementById('loading-phase').style.opacity = '0';
        document.getElementById('loading-phase').style.transform = 'scale(0.9)';
        
        setTimeout(() => {
            document.getElementById('loading-phase').style.display = 'none';
            
            if (pendingReviews.length > 0) {
                initWizard();
            } else {
                finishOnboarding();
            }
        }, 600);
    }

    function updateStackCards() {
        const activeMCard = document.querySelector('.m-ficha-card.active');
        if (activeMCard) {
            const h = activeMCard.offsetHeight;
            if (h > 0) {
                document.querySelectorAll('.m-stack-card').forEach(card => {
                    card.style.height = (h) + 'px';
                });
            }
        }
    }

    function initWizard() {
        const wizard = document.getElementById('wizard-phase');
        wizard.style.display = 'block';
        
        renderCards();
        updateProgress();

        setTimeout(() => {
            wizard.style.opacity = '1';
            wizard.style.transform = 'translateY(0)';
            updateStackCards();
        }, 50);

        // Bind mobile action bar
        document.getElementById('mobile-btn-skip').onclick = function() {
            if (currentCardIndex < pendingReviews.length) {
                skipCard(currentCardIndex);
            }
        };
        document.getElementById('mobile-btn-skip-all').onclick = function() {
            while (currentCardIndex < pendingReviews.length) {
                const rev = pendingReviews[currentCardIndex];
                evaluatedItems.push({
                    disciplina: rev.disciplina,
                    professor: rev.professor,
                    nota: null,
                    recusado: true
                });
                currentCardIndex++;
            }
            finishWizard();
        };
    window.autoRateCard = function(idx, nota, event) {
        setTimeout(() => {
            rateCard(idx, nota, event);
        }, 350);
    }
    }

    function formatProfName(fullName) {
        if (!fullName || fullName.toUpperCase() === 'DESCONHECIDO') return fullName;
        const parts = fullName.trim().split(/\s+/);
        if (parts.length <= 1) return fullName;
        const preps = ['DE', 'DA', 'DO', 'DAS', 'DOS'];
        if (parts.length > 2 && preps.includes(parts[1].toUpperCase())) {
            return parts[0] + ' ' + parts[1] + ' ' + parts[2];
        }
        return parts[0] + ' ' + parts[1];
    }

    function renderCards() {
        const mobileContainer = document.getElementById('mobile-card-stage');
        const oldCards = mobileContainer.querySelectorAll('.m-ficha-card');
        oldCards.forEach(c => c.remove());

        pendingReviews.forEach((rev, idx) => {
            const mCard = document.createElement('section');
            mCard.className = `m-ficha-card ${idx === 0 ? 'active' : ''}`;
            mCard.id = `mcard-${idx}`;
            mCard.innerHTML = `
              <div class="m-ficha-notch"></div>
              <p class="m-ficha-eyebrow">Avaliação anônima</p>
              <h1 class="m-ficha-title">${rev.disciplina}</h1>
              <p class="m-ficha-prof">Prof. ${formatProfName(rev.professor)}</p>
              <hr class="m-ficha-rule" />

              <p class="m-rating-question">Quão exigente foi esta disciplina?</p>

              <div class="m-stamp-group">
                <input type="radio" name="nota-${idx}" id="n5-${idx}" value="5" onchange="autoRateCard(${idx}, 5, event)">
                <label for="n5-${idx}" class="m-stamp">5</label>
                <input type="radio" name="nota-${idx}" id="n4-${idx}" value="4" onchange="autoRateCard(${idx}, 4, event)">
                <label for="n4-${idx}" class="m-stamp">4</label>
                <input type="radio" name="nota-${idx}" id="n3-${idx}" value="3" onchange="autoRateCard(${idx}, 3, event)">
                <label for="n3-${idx}" class="m-stamp">3</label>
                <input type="radio" name="nota-${idx}" id="n2-${idx}" value="2" onchange="autoRateCard(${idx}, 2, event)">
                <label for="n2-${idx}" class="m-stamp">2</label>
                <input type="radio" name="nota-${idx}" id="n1-${idx}" value="1" onchange="autoRateCard(${idx}, 1, event)">
                <label for="n1-${idx}" class="m-stamp">1</label>
              </div>
              <div class="m-scale-ends">
                <span>tranquila</span>
                <span>pesada</span>
              </div>
            `;
            mobileContainer.appendChild(mCard);
        });
        
        const ticksContainer = document.getElementById('mobile-tally-ticks');
        if(ticksContainer) {
            ticksContainer.innerHTML = '';
            for (let i = 0; i < pendingReviews.length; i++) {
                ticksContainer.appendChild(document.createElement('span'));
            }
        }
    }

    function updateProgress() {
        const total = pendingReviews.length;
        
        const mobileText = document.getElementById('mobile-tally-count');
        if(mobileText) mobileText.textContent = `${currentCardIndex}/${total}`;
        
        const ticks = document.getElementById('mobile-tally-ticks');
        if(ticks && ticks.children) {
            for(let i = 0; i < ticks.children.length; i++) {
                if (i < currentCardIndex) {
                    ticks.children[i].classList.add('done');
                } else {
                    ticks.children[i].classList.remove('done');
                }
            }
        }
    }

    window.rateCard = function(idx, rating, event) {
        if(event && event.currentTarget && event.currentTarget.tagName !== 'INPUT') {
            const btn = event.currentTarget;
            btn.style.transform = 'scale(0.9)';
            setTimeout(() => btn.style.transform = 'scale(1)', 150);
        }

        // save rating
        const rev = pendingReviews[idx];
        evaluatedItems.push({
            disciplina: rev.disciplina,
            professor: rev.professor,
            nota: rating,
            recusado: false
        });

        // confetti
        if (event && event.target) {
            let el = event.target;
            if (el.tagName === 'INPUT' && el.nextElementSibling) el = el.nextElementSibling;
            const rect = el.getBoundingClientRect();
            fireConfetti(rect.left + rect.width / 2, rect.top + rect.height / 2);
        } else {
            fireConfetti(window.innerWidth / 2, window.innerHeight / 2);
        }

        nextCard(idx, 'exit-right');
    }

    window.skipCard = function(idx) {
        const rev = pendingReviews[idx];
        evaluatedItems.push({
            disciplina: rev.disciplina,
            professor: rev.professor,
            nota: null,
            recusado: true
        });

        nextCard(idx, 'exit-left');
    }

    function nextCard(idx, exitClass) {
        const currentMCard = document.getElementById(`mcard-${idx}`);
        if(currentMCard) {
            currentMCard.classList.remove('active');
            currentMCard.classList.add(exitClass);
        }

        currentCardIndex++;
        updateProgress();

        if (currentCardIndex < pendingReviews.length) {
            const nMCard = document.getElementById(`mcard-${currentCardIndex}`);
            if(nMCard) {
                nMCard.classList.add('active');
                setTimeout(() => updateStackCards(), 10);
            }
        } else {
            // Finished all cards
            setTimeout(() => {
                finishWizard();
            }, 400);
        }
    }

    async function finishWizard() {
        const wizard = document.getElementById('wizard-phase');
        wizard.style.opacity = '0';
        wizard.style.transform = 'scale(0.9)';
        
        setTimeout(() => {
            wizard.style.display = 'none';
            
            // Check if evaluated enough for a trophy
            const evaluatedCount = evaluatedItems.filter(i => !i.recusado).length;
            const hasCelebration = evaluatedCount >= 3;
            if (hasCelebration) {
                fireConfetti(window.innerWidth / 2, window.innerHeight / 2);
                const cel = document.getElementById('celebration-phase');
                cel.style.display = 'block';
                setTimeout(() => {
                    cel.style.opacity = '1';
                    cel.style.transform = 'scale(1)';
                }, 50);
            } else {
                const lp = document.getElementById('loading-phase');
                document.querySelector('.status-title').textContent = "Quase lá!";
                document.getElementById('status-text').textContent = "Configurando seu Dashboard...";
                document.getElementById('ring-fg').style.strokeDashoffset = 0;
                document.getElementById('ring-pct').textContent = "100%";
                lp.style.display = 'flex';
                setTimeout(() => {
                    lp.style.opacity = '1';
                    lp.style.transform = 'scale(1)';
                }, 50);
            }

            submitAndRedirect(hasCelebration);
        }, 600);
    }

    async function submitAndRedirect(hasCelebration) {
        if (window.APP_CONFIG && window.APP_CONFIG.isTest) {
            console.log("Modo de teste: avaliações não serão enviadas.");
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, hasCelebration ? 1200 : 200);
            return;
        }

        const promises = [];
        // Submit evaluations if any
        if (evaluatedItems.length > 0) {
            promises.push(
                fetch('/api/avaliacoes/submeter', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.APP_CONFIG.csrfToken
                    },
                    body: JSON.stringify({ itens: evaluatedItems })
                }).catch(e => console.error(e))
            );
        }

        // Set onboarding complete
        promises.push(
            fetch('/api/user/complete_onboarding', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.APP_CONFIG.csrfToken
                }
            }).catch(e => console.error(e))
        );

        await Promise.all(promises);

        // Redirect after a short delay
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, hasCelebration ? 1500 : 200);
    }

    async function finishOnboarding() {
        if (window.APP_CONFIG && window.APP_CONFIG.isTest) {
            window.location.href = '/dashboard';
            return;
        }
        try {
            await fetch('/api/user/complete_onboarding', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.APP_CONFIG.csrfToken
                }
            });
        } catch(e) {}
        window.location.href = '/dashboard';
    }

    // Start
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'review') {
        document.getElementById('loading-phase').style.display = 'none';
        fetchPendingReviews().then(() => {
            if (pendingReviews.length > 0) {
                initWizard();
            } else {
                window.location.href = '/dashboard';
            }
        });
    } else {
        startLoadingPhase();
    }
});
