let data = [];
    let liveData = [];
    let isHistoryMode = false;
    let chart = null;
    let absencesChart = null;
    let historyChart = null;
    let isStreamActive = false;
    let supportCardShown = false;
    let isSupporter = false;
    let profileData = null;
    const seenIds = new Set();
    const CURRENT_USER = window.APP_CONFIG.currentUser;
    const CACHE_KEY = `grades_${CURRENT_USER}`;


    function applyMobileLayout() {
      document.body.classList.add('mobile-layout');
    }
    applyMobileLayout();
    window.addEventListener('resize', () => {
      mRenderGroupedList();
    });


    const ACTIVATE_URL_TEMPLATE = window.APP_CONFIG.urls.activateAccount.replace('999999', '__ID__');

    function activateAccount(id, initials) {
      const overlay = document.getElementById('account-switch-overlay');
      const avatarEl = document.getElementById('sw-avatar-initials');
      if (initials) avatarEl.textContent = initials.toUpperCase().slice(0, 2);
      overlay.classList.add('visible');
      document.querySelectorAll('.account-dropdown').forEach(d => d.classList.remove('show'));
      const url = ACTIVATE_URL_TEMPLATE.replace('__ID__', id);
      const body = new URLSearchParams({ csrf_token: window.APP_CONFIG.csrfToken });
      fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString() })
        .then(() => window.location.reload())
        .catch(() => window.location.reload());
    }

    function toggleAccountMenu() {
      document.getElementById('accDropdown').classList.toggle('show');
    }
    function toggleSemesterMenu() {
      document.getElementById('semDropdown').classList.toggle('show');
    }


    function toggleAccountMenuM() {
      document.getElementById('accDropdown-m').classList.toggle('show');
    }
    function toggleSemesterMenuM() {
      document.getElementById('semDropdown-m').classList.toggle('show');
    }

    window.toggleFreqDetails = function (id) {
      const details = document.getElementById(`freq-details-${id}`);
      const arrow = document.getElementById(`freq-arrow-${id}`);
      if (!details || !arrow) return;
      const isCollapsed = details.style.maxHeight === '0px' || details.style.maxHeight === '0' || details.style.maxHeight === '';
      if (isCollapsed) {
        details.style.maxHeight = '300px';
        arrow.style.transform = 'rotate(180deg)';
        details.style.marginTop = '8px';
      } else {
        details.style.maxHeight = '0px';
        arrow.style.transform = 'rotate(0deg)';
        details.style.marginTop = '0px';
      }
    };
 
    window.showFreqHelp = function (name, faltas, maxFaltas, presencas, pendentes, futuras, perSession, event) {
      if (event) event.stopPropagation();
      
      const overlay = document.createElement('div');
      overlay.style.position = 'fixed';
      overlay.style.top = '0';
      overlay.style.left = '0';
      overlay.style.width = '100vw';
      overlay.style.height = '100vh';
      overlay.style.background = 'rgba(0, 0, 0, 0.6)';
      overlay.style.backdropFilter = 'blur(6px)';
      overlay.style.display = 'flex';
      overlay.style.alignItems = 'center';
      overlay.style.justifyContent = 'center';
      overlay.style.zIndex = '99999';
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.3s ease';
      
      const daysPresencas = Math.floor(presencas / perSession);
      const daysFaltas = Math.floor(faltas / perSession);
      const daysMaxFaltas = Math.floor(maxFaltas / perSession);
      const daysPendentes = Math.floor(pendentes / perSession);
      const daysFuturas = Math.floor(futuras / perSession);
      
      const content = document.createElement('div');
      content.className = 'card';
      content.style.width = '90%';
      content.style.maxWidth = '400px';
      content.style.padding = '24px';
      content.style.borderRadius = '16px';
      content.style.border = '1px solid var(--border)';
      content.style.background = 'var(--bg-card)';
      content.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.5)';
      content.style.transform = 'scale(0.95)';
      content.style.transition = 'transform 0.3s ease';
      
      content.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;">
          <div style="font-size:16px; font-weight:800; color:#fff; padding-right:16px;">Cálculo de Frequência</div>
          <span style="font-size:18px; color:var(--text-muted); cursor:pointer; line-height: 1;" onclick="this.closest('.freq-help-overlay').remove()">✕</span>
        </div>
        <div style="font-size:13px; font-weight:700; color:var(--accent); margin-bottom:12px; text-transform:uppercase;">${name}</div>
        <p style="font-size:12px; color:var(--text-muted); margin:0 0 16px 0; line-height:1.5;">
          Esta disciplina possui uma carga horária diária de <strong>${perSession} horas-aula</strong>.
          Para facilitar o controle, todos os valores são convertidos para <strong>dias de aula</strong> (encontros).
        </p>
        
        <div style="display:flex; flex-direction:column; gap:10px; font-size:12px; border-top:1px solid var(--border); padding-top:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--success)">✅ Presença:</span>
            <span style="font-weight:700; color:#fff;">${daysPresencas} ${daysPresencas === 1 ? 'dia' : 'dias'} <span style="font-weight:500; color:var(--text-muted); font-size:11px;">(${presencas}h / ${perSession}h)</span></span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--danger)">❌ Faltas:</span>
            <span style="font-weight:700; color:#fff;">${daysFaltas} ${daysFaltas === 1 ? 'dia' : 'dias'} <span style="font-weight:500; color:var(--text-muted); font-size:11px;">(${faltas}h / ${perSession}h)</span></span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--text-muted)">⚠️ Limite Permitido:</span>
            <span style="font-weight:700; color:#fff;">${daysMaxFaltas} ${daysMaxFaltas === 1 ? 'dia' : 'dias'} <span style="font-weight:500; color:var(--text-muted); font-size:11px;">(${maxFaltas}h / ${perSession}h)</span></span>
          </div>
          ${pendentes > 0 ? `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--warning)">⚠️ Pendente:</span>
            <span style="font-weight:700; color:#fff;">${daysPendentes} ${daysPendentes === 1 ? 'dia' : 'dias'} <span style="font-weight:500; color:var(--text-muted); font-size:11px;">(${pendentes}h / ${perSession}h)</span></span>
          </div>` : ''}
          ${futuras > 0 ? `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:var(--text-muted)">⬜ Futuras:</span>
            <span style="font-weight:700; color:#fff;">${daysFuturas} ${daysFuturas === 1 ? 'dia' : 'dias'} <span style="font-weight:500; color:var(--text-muted); font-size:11px;">(${futuras}h / ${perSession}h)</span></span>
          </div>` : ''}
        </div>
        
        <button onclick="this.closest('.freq-help-overlay').remove()" style="margin-top:20px; width:100%; background:var(--accent); color:#fff; border:none; padding:10px 0; border-radius:12px; font-weight:700; cursor:pointer; outline:none;">
          Entendido
        </button>
      `;
      
      overlay.className = 'freq-help-overlay';
      overlay.appendChild(content);
      document.body.appendChild(overlay);
      
      setTimeout(() => {
        overlay.style.opacity = '1';
        content.style.transform = 'scale(1)';
      }, 10);
      
      overlay.onclick = function (e) {
        if (e.target === overlay) {
          overlay.remove();
        }
      };
    };

    window.onclick = function (event) {
      if (!event.target.closest('.account-dropdown')) {
        document.querySelectorAll('.account-dropdown').forEach(d => d.classList.remove('show'));
      }
    };


    window.switchTab = function (viewId) {
      document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('view-' + viewId).classList.add('active');
      const buttons = document.querySelectorAll('.tab-btn');
      if (viewId === 'list') buttons[0].classList.add('active');
      else if (viewId === 'stats') { buttons[1].classList.add('active'); renderChart(); loadAcademicProfile(); }
      else if (viewId === 'frequency') { buttons[2].classList.add('active'); renderFrequency(); }
      else if (viewId === 'achievements') { buttons[3].classList.add('active'); renderAchievements(); }
      else if (viewId === 'matricula') { if (buttons[4]) buttons[4].classList.add('active'); loadMatricula(); }
    };


    function mSwitchTab(viewId, btn) {
      // views
      document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
      document.getElementById('view-' + viewId).classList.add('active');
      // seg ctrl
      document.querySelectorAll('.m-seg-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // bottom nav
      document.querySelectorAll('.m-nav-btn').forEach(b => b.classList.remove('active'));
      const navBtn = document.getElementById('m-nav-' + viewId);
      if (navBtn) navBtn.classList.add('active');
      updateHeader();
      // side effects
      if (viewId === 'stats') { renderChart(); loadAcademicProfile(); }
      if (viewId === 'frequency') renderFrequency();
      if (viewId === 'achievements') renderAchievements();
      if (viewId === 'matricula') loadMatricula();
    }

    function mSwitchTabFromNav(viewId) {
      // views
      document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
      document.getElementById('view-' + viewId).classList.add('active');
      // bottom nav
      document.querySelectorAll('.m-nav-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('m-nav-' + viewId).classList.add('active');
      updateHeader();
      // side effects
      if (viewId === 'stats') { renderChart(); loadAcademicProfile(); }
      if (viewId === 'frequency') renderFrequency();
      if (viewId === 'achievements') renderAchievements();
      if (viewId === 'matricula') loadMatricula();
      // scroll topo
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // ----------------- ONLINE ENROLLMENT JAVASCRIPT LOGIC -----------------
    // ----------------- ONLINE ENROLLMENT JAVASCRIPT LOGIC -----------------
    let matriculaLevels = [];
    let allDisciplines = []; // flattened for easy access
    let picked = {}; // discCode -> classId
    let matriculaViewState = '';
    let isMatriculaLoaded = false;
    let stage = 1;

    const DIAS = ['Segunda','Terça','Quarta','Quinta','Sexta','Sábado'];
    const dayCodes = [2, 3, 4, 5, 6, 7];
    const BLOCOS = [
      {id:'M1', s:'07:00'}, {id:'M2', s:'07:55'}, {id:'M3', s:'08:55'}, {id:'M4', s:'09:50'}, {id:'M5', s:'10:50'}, {id:'M6', s:'11:45'},
      {id:'T1', s:'13:00'}, {id:'T2', s:'13:55'}, {id:'T3', s:'14:55'}, {id:'T4', s:'15:50'}, {id:'T5', s:'16:50'}, {id:'T6', s:'17:45'},
      {id:'N1', s:'18:45'}, {id:'N2', s:'19:40'}, {id:'N3', s:'20:30'}, {id:'N4', s:'21:20'}
    ];

    function parseSchedule(scheduleStr) {
      if(!scheduleStr) return [];
      const regex = /^([2-7]+)([MNT])([1-6]+)$/;
      const match = scheduleStr.match(regex);
      if (!match) return [];
      const days = match[1].split('').map(Number);
      const shift = match[2];
      const hours = match[3].split('').map(Number);
      const slots = [];
      days.forEach(d => {
        hours.forEach(h => {
          slots.push(`${d}-${shift}${h}`);
        });
      });
      return slots;
    }

    function startMatriculaFlow() {
      const btn = document.querySelector('#matricula-intro-card .m-btn-primary');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = 'Carregando turmas...';

      fetch('/api/matricula/status')
        .then(res => res.json())
        .then(data => {
          if (data.error) throw new Error(data.error);
          matriculaLevels = data.levels || [];
          matriculaViewState = data.view_state || '';
          isMatriculaLoaded = true;
          let availableDiscs = [];
          let emptyDiscs = [];
          matriculaLevels.forEach(l => {
            l.disciplines.forEach(d => {
              const fullD = {...d, level: l.level};
              if (d.classes && d.classes.length > 0) availableDiscs.push(fullD);
              else emptyDiscs.push(fullD);
            });
          });
          allDisciplines = availableDiscs.concat(emptyDiscs);

          const introCard = document.getElementById('matricula-intro-card');
          const flowWrap = document.getElementById('matricula-flow-wrap');
          const stepper = document.getElementById('stepper');
          
          if (introCard) introCard.style.display = 'none';
          if (flowWrap) flowWrap.style.display = 'block';
          if (stepper) stepper.style.display = 'flex';
          document.getElementById('bbar').style.display = 'flex';
          
          go(1);
        })
        .catch(err => alert('Erro: ' + err.message))
        .finally(() => { btn.disabled = false; btn.innerHTML = originalText; });
    }

    function renderStepper() {
      const LABELS=['Escolher','Revisar','Confirmar'];
      document.getElementById('stepper').innerHTML=LABELS.map((l,i)=>{
        const n=i+1, st=n<stage?'done':n===stage?'active':'';
        const dot=n<stage
          ?`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
          :n;
        const line=i<LABELS.length-1
          ?`<div class="stp-line ${n<stage?'done':''}"></div>`:'';
        return `<div class="stp ${st}"><div class="stp-n">${dot}</div><div class="stp-l">${l}</div></div>${line}`;
      }).join('');
    }

    window.go = function(n) {
      stage = n;
      document.querySelectorAll('.stage').forEach(s => s.classList.remove('on'));
      document.getElementById('s'+n).classList.add('on');
      document.getElementById('bbar').style.display = n===1 ? 'flex' : 'none';
      if(n === 1) renderDiscs();
      if(n === 2) renderReview();
      if(n === 3) renderConfirm();
      renderStepper();
      window.scrollTo({top:0,behavior:'smooth'});
    };

    let firstRender = true;
    let prevConflictedCodes = new Set();
    let lastCount = 0;

    function exigColor(v){
      if (v < 1.5) return '#10b981';
      if (v < 2.5) return '#8bc34a';
      if (v < 3.5) return '#f59e0b';
      if (v < 4.5) return '#f97316';
      return '#ef4444';
    }
    const STAR = '<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';
    const CHECK = '<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    const WARN_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    const dayNames = {2:'Seg',3:'Ter',4:'Qua',5:'Qui',6:'Sex',7:'Sáb'};

    function humanSchedule(scheduleStr){
      if(!scheduleStr) return scheduleStr;
      const m = scheduleStr.match(/^([2-7]+)([MNT])([1-6]+)$/);
      if(!m) return scheduleStr;
      const days = m[1].split('').map(n => dayNames[n]).join('/');
      const shift = m[2];
      const hours = m[3].split('');
      const firstBloco = BLOCOS.find(b => b.id === shift + hours[0]);
      const codes = hours.map(h => shift + h).join('–');
      return `${days} · ${codes} · ${firstBloco ? firstBloco.s : ''}`;
    }

    function buildSlotMap(){
      const map = {};
      Object.entries(picked).forEach(([code, cid]) => {
        const d = allDisciplines.find(x => x.code === code);
        if(!d) return;
        const t = d.classes.find(x => x.class_id == cid);
        if(!t) return;
        parseSchedule(t.schedule).forEach(slot => {
          if(!map[slot]) map[slot] = [];
          map[slot].push({ code: d.code, teacher: t.teacher, name: d.name, t: t });
        });
      });
      return map;
    }

    function buildConflictMap(slotMap){
      const map = {}; 
      Object.values(slotMap).forEach(arr => {
        if(arr.length > 1){
          arr.forEach(e => {
            if(!map[e.code]) map[e.code] = new Set();
            arr.forEach(o => { if(o.code !== e.code) map[e.code].add(o.code); });
          });
        }
      });
      return map;
    }

    function bump(el){
      el.classList.remove('bump');
      void el.offsetWidth; 
      el.classList.add('bump');
    }

    function renderDiscs() {
      if(allDisciplines.length === 0){
        document.getElementById('ficha-list').innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">Nenhuma turma encontrada.</div>';
        return;
      }
      
      const slotMap = buildSlotMap();
      const conflictMap = buildConflictMap(slotMap);
      const list = document.getElementById('ficha-list');

      list.innerHTML = allDisciplines.map((d, i) => {
        const cid = picked[d.code];
        const isFilled = cid !== undefined;
        const conflicts = conflictMap[d.code];
        const isConflict = !!conflicts;
        const isNewConflict = isConflict && !prevConflictedCodes.has(d.code);

        const formatProf = (name) => {
          if (!name || name === 'A definir') return 'A definir';
          return name.split(' ')
            .filter(p => !['de', 'da', 'do', 'das', 'dos'].includes(p.toLowerCase()))
            .slice(0, 2)
            .join(' ');
        };

        let pillsHtml = '';
        if(d.classes && d.classes.length > 0){
          pillsHtml = d.classes.map((t) => `
            <button class="pill ${cid == t.class_id ? 'sel' : ''}" data-code="${d.code}" data-cid="${t.class_id}" onclick="selectTurma('${escapeHtml(d.code)}', '${escapeHtml(String(t.class_id))}')">
              <span class="pill-check">${CHECK}</span>
              <span class="pill-code">
                Turma ${escapeHtml(t.class_code.replace(/^Turma\s+/i, ''))} · ${escapeHtml(formatProf(t.teacher))}
                ${t.media ? `<span style="display:inline-flex; align-items:center; gap:2px; color:${exigColor(t.media)}; font-size: 9px; opacity: 0.9; transform: translateY(-0.5px);">${STAR} ${t.media}</span>` : ''}
              </span>
              <span class="pill-prof">${escapeHtml(humanSchedule(t.schedule))}</span>
              <span class="pill-sigaa">SIGAA ${escapeHtml(t.schedule)}</span>
            </button>`).join('');
        } else {
          pillsHtml = `<div style="font-size:12px; color:var(--text-muted); font-style:italic; padding: 4px 0;">Nenhuma turma com vagas disponíveis no momento.</div>`;
        }

        let conflictNote = '';
        if(isConflict){
          const detail = [...conflicts].map(c => {
            const other = allDisciplines.find(x => x.code === c);
            const otherTurma = other.classes.find(x => x.class_id == picked[c]);
            return `${other.name} (${humanSchedule(otherTurma.schedule)})`;
          }).join('; ');
          conflictNote = `
          <div class="fr-conflict-note ${isNewConflict ? 'note-in' : ''}">
            ${WARN_ICON}
            <span><strong>Conflito de horário</strong> com ${detail}.</span>
          </div>`;
        }

        let gradeHtml = '';
        if (d.media !== undefined && d.media !== null) {
          gradeHtml = `<span class="exig" style="color:${exigColor(d.media)}">${STAR} ${d.media}</span>`;
        }

        return `
        <div class="ficha-row ${isFilled ? 'filled' : ''} ${isConflict ? 'conflict' : ''} ${firstRender ? 'row-in' : ''}" data-disc-code="${escapeHtml(d.code)}" ${firstRender ? `style="animation-delay:${i*35}ms"` : ''}>
          <div class="fr-num">${String(i+1).padStart(2,'0')}</div>
          <div class="fr-body">
            <div class="fr-head">
              <div>
                <div class="fr-name">${escapeHtml(d.name)}</div>
                <span class="fr-code">${escapeHtml(d.code)}</span>
              </div>
              ${gradeHtml}
            </div>
            <div class="fr-pills">${pillsHtml}</div>
            ${conflictNote}
          </div>
        </div>`;
      }).join('');

      prevConflictedCodes = new Set(Object.keys(conflictMap));
      firstRender = false;

      renderTally();
    }

    function renderTally(){
      const total = allDisciplines.length;
      const count = Object.keys(picked).length;

      document.getElementById('tally-count').textContent = String(count).padStart(2,'0');
      document.getElementById('tally-total').textContent = String(total).padStart(2,'0');
      document.getElementById('bb-count').textContent = count;
      document.getElementById('bb-total').textContent = total;

      if(count !== lastCount){
        bump(document.getElementById('tally-count'));
        bump(document.getElementById('bb-count'));
        lastCount = count;
      }

      const slotMap = buildSlotMap();
      const hasConflict = Object.keys(buildConflictMap(slotMap)).length > 0;

      document.getElementById('conflict-badge').classList.toggle('show', hasConflict);
      document.getElementById('bbar').classList.toggle('has-conflict', hasConflict);

      const btn = document.getElementById('bb-btn');
      btn.disabled = count === 0;
      btn.classList.toggle('danger', hasConflict);
      btn.innerHTML = hasConflict
        ? `${WARN_ICON} Resolver conflito de horário`
        : 'Continuar para revisão →';
    }

    window.selectTurma = function(discCode, classId) {
      const wasSelected = picked[discCode] == classId;
      if(wasSelected) delete picked[discCode]; 
      else picked[discCode] = String(classId);
      
      renderDiscs();

      if(!wasSelected){
        requestAnimationFrame(() => {
          const el = document.querySelector(`.pill[data-code="${discCode}"][data-cid="${classId}"]`);
          if(el){
            el.classList.add('just-picked');
            setTimeout(() => el.classList.remove('just-picked'), 450);
          }
        });
      }
    };
    
    window.handleContinue = function(){
      const slotMap = buildSlotMap();
      const conflictMap = buildConflictMap(slotMap);
      const codes = Object.keys(conflictMap);
      if(codes.length > 0){
        const rowEl = document.querySelector(`.ficha-row[data-disc-code="${codes[0]}"]`);
        if(rowEl){
          rowEl.scrollIntoView({ behavior:'smooth', block:'center' });
          rowEl.classList.remove('flash'); void rowEl.offsetWidth;
          rowEl.classList.add('flash');
        }
        return;
      }
      go(2);
    };

    window.remove = function(discCode) {
      delete picked[discCode];
      renderReview();
    };

    function pickedList() {
      const list = [];
      Object.entries(picked).forEach(([code, cid]) => {
        const d = allDisciplines.find(x => x.code === code);
        if(d) {
          const c = d.classes.find(x => x.class_id == cid);
          if(c) {
            list.push({ ...c, dNome: d.name, dCod: d.code, dMedia: d.media });
          }
        }
      });
      return list;
    }

    function clashData(list) {
      const occ = {};
      list.forEach(t => {
        const slots = parseSchedule(t.schedule);
        slots.forEach(s => {
          (occ[s] = occ[s] || []).push(t);
        });
      });
      const keys = new Set(), ids = new Set();
      Object.entries(occ).forEach(([k, arr]) => {
        if(arr.length > 1) { keys.add(k); arr.forEach(t => ids.add(t.class_id)); }
      });
      return { keys, ids };
    }

    function renderReview() {
      const list = pickedList();
      const {keys, ids} = clashData(list);

      // table
      let html=`<tr><th></th>${DIAS.map(d=>`<th>${d}</th>`).join('')}</tr>`;
      BLOCOS.forEach(b => {
        html+=`<tr><th style="color:var(--text-muted);font-size:9px;">${b.s}</th>`;
        dayCodes.forEach(dia => {
          const k = `${dia}-${b.id}`;
          const t = list.find(x => parseSchedule(x.schedule).includes(k));
          const cls = t ? (keys.has(k) ? 'clash' : 'on') : '';
          html+=`<td class="${cls}">${t ? escapeHtml(t.dCod) : ''}</td>`;
        });
        html+='</tr>';
      });
      document.getElementById('tgrid').innerHTML=html;

      const cn = document.getElementById('clash-note');
      if(keys.size){ cn.classList.add('on'); cn.textContent='Há choque de horário entre turmas selecionadas. Volte e ajuste antes de continuar.'; }
      else cn.classList.remove('on');

      document.getElementById('rev-list').innerHTML = list.length
        ? list.map(t=>`
          <div class="rv-item">
            <div class="rv-dot ${ids.has(t.class_id)?'clash':''}"></div>
            <div class="rv-main">
              <div class="rv-name">${escapeHtml(t.dNome)}</div>
              <div class="rv-meta">${escapeHtml(t.dCod)} · ${escapeHtml(t.teacher)} · ${escapeHtml(t.schedule)}</div>
            </div>
            <button class="rv-rmv" onclick="remove('${escapeHtml(t.dCod)}')">Remover</button>
          </div>`).join('')
        :`<div style="font-size:12px;color:var(--text-muted);padding:4px 0;">Nenhuma turma selecionada.</div>`;

      document.getElementById('btn23').disabled = list.length === 0 || keys.size > 0;

      // Gráfico de Avaliações
      const chartCard = document.getElementById('rev-chart-card');
      if (list.length > 0 && typeof Chart !== 'undefined') {
        chartCard.style.display = 'block';
        const ctx = document.getElementById('revChartCanvas').getContext('2d');
        if (window.revChart) window.revChart.destroy();
        window.revChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: list.map(t => t.dCod),
            datasets: [{
              label: 'Nível de Exigência (Disc + Prof)',
              data: list.map(t => (t.dMedia || 0) + (t.media || 0)),
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56,189,248,0.2)',
              fill: true,
              tension: 0.3
            }]
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, max: 10, grid: { color: 'rgba(255,255,255,0.1)' } },
              x: { ticks: { color: '#999', font: { size: 10 } }, grid: { display: false } }
            }
          }
        });
      } else {
        if(chartCard) chartCard.style.display = 'none';
      }
    }

    function renderConfirm() {
      // Removido a pedido do usuário (agora a tela 3 só tem a senha)
      document.getElementById('pwd').value = '';
    }

    window.finalize = function() {
      const pwd = document.getElementById('pwd').value.trim();
      const err = document.getElementById('pwd-err');
      if(!pwd) { err.classList.add('on'); err.innerText='Digite sua senha para continuar.'; return; }
      err.classList.remove('on');
      
      const btn = document.getElementById('btn-finalize');
      btn.disabled = true;
      btn.innerText = 'Assinando...';

      const selectedClassIds = pickedList().map(x => x.class_id);

      fetch('/api/matricula/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
        body: JSON.stringify({ selected_class_ids: selectedClassIds, view_state: matriculaViewState })
      })
      .then(res => {
        if (!res.ok) throw new Error('Erro ao processar as turmas selecionadas.');
        return fetch('/api/matricula/confirm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
          body: JSON.stringify({ password: pwd })
        });
      })
      .then(res => res.json().then(data => {
        if (!res.ok) throw new Error(data.message || 'Senha incorreta ou erro de validação.');
        return data;
      }))
      .then(data => {
        document.getElementById('proto-n').textContent = 'SIGAA-' + Math.floor(1e5 + Math.random()*9e5);
        document.getElementById('suc-list').innerHTML = pickedList().map(t=>`
          <div class="suc-row">
            <div style="flex:1">
              <div style="font-size:12.5px;font-weight:700;color:var(--text-main);">${escapeHtml(t.dNome)}</div>
              <div style="font-size:10.5px;color:var(--text-muted);margin-top:2px;">${escapeHtml(t.dCod)} · ${escapeHtml(t.schedule)}</div>
            </div>
            <div class="suc-ok">Gravada</div>
          </div>`).join('');
        
        stage = 4;
        document.querySelectorAll('.stage').forEach(s=>s.classList.remove('on'));
        document.getElementById('s4').classList.add('on');
        document.getElementById('bbar').style.display='none';
        document.getElementById('stepper').style.display='none';
        window.scrollTo({top:0,behavior:'smooth'});
      })
      .catch(e => {
        err.innerText = e.message;
        err.classList.add('on');
      })
      .finally(() => {
        btn.disabled = false;
        btn.innerText = 'Confirmar e assinar';
      });
    };

    window.restartMatriculaWizard = function() {
      picked = {};
      document.getElementById('pwd').value = '';
      document.getElementById('stepper').style.display = 'none';
      document.getElementById('s4').classList.remove('on');
      document.getElementById('matricula-intro-card').style.display = 'block';
    };

    function loadMatricula() {
      if (isMatriculaLoaded) return;
    }


    function togglePrivacy() {
      document.body.classList.toggle('privacy-active');
    }


    function showSupportCard() {
      if (supportCardShown) return;
      supportCardShown = true;
      mRenderGroupedList();
    }
    setTimeout(() => { if (!isStreamActive) return; showSupportCard(); }, 5000);


    function escapeHtml(unsafe) {
      if (!unsafe) return '';
      return unsafe.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
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
    
    // Helper to hide the row if both widgets are hidden
    function updateWidgetsRowVisibility() {
        const wRow = document.getElementById('m-widgets-row');
        const wStatus = document.getElementById('m-status-widget');
        const wDiff = document.getElementById('m-diff-widget');
        if (wRow && wStatus && wDiff) {
            if (wStatus.style.display === 'none' && wDiff.style.display === 'none') {
                wRow.style.display = 'none';
            } else {
                wRow.style.display = 'flex';
            }
        }
    }

    function renderDifficultyWidget(average) {
        const widget = document.getElementById('m-diff-widget');
        if (!widget) return;
        
        const widgetVal = document.getElementById('m-diff-val');
        const svgCircle = widget.querySelector('.ring-container svg circle:nth-child(2)');
        const svgBgCircle = widget.querySelector('.ring-container svg circle:nth-child(1)');
        const iconSpan = document.getElementById('m-diff-icon');

        if (average === null || average === undefined) {
            widget.style.display = 'none';
            updateWidgetsRowVisibility();
            return;
        }

        widget.style.display = 'flex';
        updateWidgetsRowVisibility();
        
        let text = 'Altíssima Exigência';
        let colorRgb = '244, 67, 54';
        let hexColor = '#f44336';
        let displayAvg = (Math.round(average * 10) / 10).toFixed(1);
        
        if (average < 1.5) { text = 'Baixa Exigência'; colorRgb = '76, 175, 80'; hexColor = '#4caf50'; } 
        else if (average < 2.5) { text = 'Leve'; colorRgb = '139, 195, 74'; hexColor = '#8bc34a'; } 
        else if (average < 3.5) { text = 'Médio'; colorRgb = '250, 204, 21'; hexColor = '#facc15'; } 
        else if (average < 4.5) { text = 'Difícil'; colorRgb = '255, 152, 0'; hexColor = '#ff9800'; }

        if (widgetVal) widgetVal.textContent = text;
        widget.style.setProperty('--sw-rgb', colorRgb);
        widget.style.setProperty('--sw-color', hexColor);
        
        if (svgCircle) {
            svgCircle.setAttribute('stroke', hexColor);
            let offset = 119 * (1 - (average / 5));
            svgCircle.setAttribute('stroke-dashoffset', offset);
        }
        if (svgBgCircle) svgBgCircle.setAttribute('stroke', `rgba(${colorRgb}, 0.15)`);
        
        if (iconSpan) {
            iconSpan.textContent = displayAvg;
        }
    }
    function roundSigga(val) { return Math.round(val * 2) / 2; }
    // Nome usado para casar avaliações: o formato "CODIGO - NOME" do histórico.
    // A exibição continua usando d.name (sem o código).
    function reviewName(item) { return (item && (item.review_name || item.name)) || ''; }

    // Expõe o código da turma no console para inspeção (window.sigaaTurmas mostra tudo).
    window.sigaaTurmas = window.sigaaTurmas || {};
    function logCourseCode(nome, d) {
      if (!d) return;
      const info = {
        disciplina: nome,
        codigo: d.code || null,
        nome_avaliacao: d.review_name || null,
        professor: d.professor || null,
        sala_horario: d.schedule_code || null,
        turma_key: d.turma_id || null,
        exigencia_media: d.exigencia_media ?? null
      };
      window.sigaaTurmas[d.code || nome] = info;
      console.log(
        `%c[SIGAA]%c ${info.codigo || '(sem código)'} %c${nome}`,
        'color:#0284c7;font-weight:bold', 'color:#16a34a;font-weight:bold', 'color:inherit',
        info
      );
    }
    function deepEqual(obj1, obj2) {
      if (obj1 === obj2) return true;
      if (typeof obj1 !== 'object' || obj1 === null || typeof obj2 !== 'object' || obj2 === null) return false;
      const keys1 = Object.keys(obj1), keys2 = Object.keys(obj2);
      if (keys1.length !== keys2.length) return false;
      for (let key of keys1) { if (!keys2.includes(key) || !deepEqual(obj1[key], obj2[key])) return false; }
      return true;
    }


    async function startDataStream() {
      const isDemo = window.location.pathname === '/demo';
      if (isDemo) {
        document.body.insertAdjacentHTML('afterbegin', `
        <div style="background:var(--warning); color:#000; text-align:center; padding:8px; font-weight:700; font-size:12px; position:sticky; top:0; z-index:9999;">
          MODO DEMONSTRAÇÃO - DADOS FICTÍCIOS
        </div>
      `);
      }
      if (!isDemo) {
        // LocalStorage cache persistence removed to ensure fresh fetch from server
        // Endpoint rate limiting protects against abuse.
      }
      let priorityIndices = [];
      let skipIndices = [];
      const SYNC_THRESHOLD = 5 * 60 * 1000; // 5 minutes
      if (liveData.length > 0) {
        priorityIndices = liveData.map(d => (d.status && d.status.is_critical) ? d.id : null).filter(id => id !== null);
        skipIndices = liveData.filter(d => d.sync_time && (Date.now() - d.sync_time < SYNC_THRESHOLD)).map(d => d.id);
      }
      isStreamActive = true;
      const st = document.getElementById('m-status-text');
      if (st) {
        st.textContent = 'Conectando...';
        st.classList.add('visible');
      }
      document.getElementById('global-sync-indicator').style.display = 'block';
      const updatedCourseIds = new Set();
      try {
        let endpoint = isDemo ? '/api/stream_demo' : '/api/stream_grades';
        let params = new URLSearchParams();
        if (!isDemo) {
          if (priorityIndices.length > 0) params.set('priority', priorityIndices.join(','));
          if (skipIndices.length > 0) params.set('skip', skipIndices.join(','));
          if (params.toString()) endpoint += '?' + params.toString();
        }
        // Reaproveita a requisição disparada no <head> (early fetch) quando aplicável.
        let response = null;
        if (!isDemo && !params.toString() && window.__earlyStream) {
          const early = window.__earlyStream;
          window.__earlyStream = null;
          response = await early;
        }
        if (!response) response = await fetch(endpoint);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();
          for (const line of lines) {
            if (!line.trim()) continue;
            try { handleStreamMessage(JSON.parse(line), updatedCourseIds); } catch (e) { }
          }
        }
        // Pruning is now handled by 'sync_end' message to ensure full completion
    } catch (e) {
        console.error("Stream error:", e);
        const tr = document.getElementById('totalResume');
        if (tr) tr.textContent = "Erro na conexão.";
      } finally {
        isStreamActive = false;
        document.getElementById('global-sync-indicator').style.display = 'none';
        if (!isHistoryMode) {
          const st = document.getElementById('m-status-text');
          if (st) {
            if (st.textContent.includes('Notas') || st.textContent.includes('Conectando')) {
              st.textContent = 'OK';
              setTimeout(() => { if (!isHistoryMode && st.textContent === 'OK') st.classList.remove('visible'); }, 3000);
            }
          }
        }
        // Stop all resilient animations
        liveData.forEach(d => { d.isRefreshing = false; d._loadingStep = null; });
        if (!isHistoryMode) { data = liveData; mRenderGroupedList(); }
        saveGradesState();
      }
    }

    function pruneStaleCourses(validIds) {
      if (!validIds) return;
      const initialCount = liveData.length;
      const validStrIds = new Set([...validIds].map(id => String(id)));
      liveData = liveData.filter(d => validStrIds.has(String(d.id)));
      if (liveData.length !== initialCount) {
        if (!isHistoryMode) { data = liveData; mRenderGroupedList(); updateHeader(); }
      }
    }

    function saveGradesState() {
      // LocalStorage state saving removed
    }

    function handleStreamMessage(msg, updatedCourseIds) {
      if (msg.error) {
        if (msg.error === "Session expired") {
          const strip = document.getElementById('m-alert-strip');
          if (strip) {
            strip.innerHTML = `⚠️ <strong>Conexão perdida:</strong> Tentando reconectar automaticamente ao SIGAA... <div class="loading-spinner" style="width:14px;height:14px;display:inline-block;border-width:2px;margin-left:8px;vertical-align:middle;border-left-color:currentColor;"></div>`;
            strip.style.background = 'rgba(59,130,246,0.1)';
            strip.style.borderLeftColor = '#3b82f6';
            strip.style.color = '#3b82f6';
            strip.classList.add('visible');
          }
          fetch('/dashboard?reauth=1').then(res => {
            if (res.url.includes('/profile') || res.url.includes('/login')) {
              if (strip) {
                strip.innerHTML = `⚠️ <strong>Sessão expirada:</strong> Não foi possível reconectar automaticamente. <a href="/profile" style="color:inherit;text-decoration:underline;">Verifique suas credenciais</a>`;
                strip.style.background = 'rgba(239,68,68,0.1)';
                strip.style.borderLeftColor = '#ef4444';
                strip.style.color = '#ef4444';
              }
            } else {
              if (strip) strip.classList.remove('visible');
              startDataStream();
            }
          }).catch(err => {
              if (strip) {
                strip.innerHTML = `⚠️ <strong>Erro:</strong> Falha de rede ao tentar reconectar. <a href="javascript:location.reload()" style="color:inherit;text-decoration:underline;">Atualizar página</a>`;
                strip.style.background = 'rgba(239,68,68,0.1)';
                strip.style.borderLeftColor = '#ef4444';
                strip.style.color = '#ef4444';
              }
          });
        }
        else if (msg.is_questionnaire) {
          const strip = document.getElementById('m-alert-strip');
          if (strip) {
            strip.innerHTML = `⚠️ <strong>Atenção:</strong> ${escapeHtml(msg.error)}`;
            strip.style.background = 'rgba(250,204,21,0.1)';
            strip.style.borderLeftColor = '#facc15';
            strip.style.color = '#facc15';
            strip.dataset.mode = 'questionnaire';
            strip.classList.add('visible');
          }
        }
        return;
      }
      if (msg.id !== undefined && updatedCourseIds) updatedCourseIds.add(msg.id);

      if (msg.type === 'user_info') {
        isSupporter = msg.is_supporter;
        supportCardShown = !isSupporter;
      } else if (msg.type === 'course_loading') {
        const idx = liveData.findIndex(d => String(d.id) === String(msg.id));
        if (idx !== -1) {
          if (msg.step === 'done') {
            liveData[idx].isRefreshing = false;
            liveData[idx]._loadingStep = null;
          } else {
            liveData[idx].isRefreshing = true;
            liveData[idx]._loadingStep = msg.step;
          }
          if (!isHistoryMode) { data = liveData; mRenderGroupedList(); }
        }
      } else if (msg.type === 'course_start') {
        addOrUpdateCourse({ id: String(msg.id), name: msg.name, obs: msg.obs, isRefreshing: true });
        document.getElementById('empty-list-msg').style.display = 'none';
        if (!isHistoryMode) {
          const st = document.getElementById('m-status-text');
          if (st) {
            st.textContent = 'Notas...';
            st.classList.add('visible');
          }
        }
      } else if (msg.type === 'sync_start') {
          if (msg.total_courses === 0 && !isHistoryMode) {
              mRenderGroupedList();
          }
      } else if (msg.type === 'profile_data') {
        profileData = msg.data;
        _buildMSemDropdown('Atual');
        checkPendingReviews();
      } else if (msg.type === 'course_data') {
        const idx = liveData.findIndex(d => String(d.id) === String(msg.id));
        if (idx !== -1) {
          logCourseCode(liveData[idx].name, msg.data);
          const current = liveData[idx];
          const isNew = current.grades && current.grades.length > 0 ? !deepEqual(current.grades, msg.data.grades) : false;
          liveData[idx] = { ...liveData[idx], ...msg.data, id: String(msg.data.id || msg.id), isLoading: false, isNew: isNew, sync_time: Date.now() };
          if (!isHistoryMode) {
            data = liveData; mRenderGroupedList(); updateHeader();
            if (isNew) {
              setTimeout(() => {
                const i = data.findIndex(d => String(d.id) === String(msg.id));
                if (i !== -1) { data[i].isNew = false; mRenderGroupedList(); }
              }, 5000);
            }
          }
        }
      } else if (msg.type === 'sync_end') {
          if (!profileData || !profileData.history_raw || Object.keys(profileData.history_raw).length === 0) {
              loadAcademicProfile(true, true); // silent background fetch, forced to bypass empty cache
          }
      } else if (msg.type === 'course_skipped') {
        const idx = liveData.findIndex(d => String(d.id) === String(msg.id));
        if (idx !== -1) {
          liveData[idx].isRefreshing = false;
          liveData[idx].isLoading = false;
          if (!isHistoryMode) { data = liveData; mRenderGroupedList(); }
        }
      } else if (msg.type === 'course_frequency') {
        const idx = liveData.findIndex(d => String(d.id) === String(msg.id));
        if (idx !== -1) {
          liveData[idx] = { ...liveData[idx], id: String(msg.id), frequency: msg.data };
          if (!isHistoryMode) {
            data = liveData;
            if (document.getElementById('view-frequency').classList.contains('active')) renderFrequency();
          }
        }
      } else if (msg.type === 'sync_end') {
        if (Object.keys(window.sigaaTurmas || {}).length) {
          console.log('%c[SIGAA] Códigos das turmas — inspecione com window.sigaaTurmas', 'color:#0284c7;font-weight:bold');
          console.table(window.sigaaTurmas);
        }
        pruneStaleCourses(updatedCourseIds);
        mRenderGroupedList(); // Ensures empty state is shown if data is 0
      }
    }

    function addOrUpdateCourse(courseObj) {
      if (courseObj.id !== undefined) courseObj.id = String(courseObj.id);
      const idx = liveData.findIndex(d => String(d.id) === String(courseObj.id));
      if (idx !== -1) liveData[idx] = { ...liveData[idx], ...courseObj };
      else liveData.push(courseObj);
      if (!isHistoryMode) { data = liveData; mRenderGroupedList(); }
    }


    let _renderTimer = null;
    let _needsRender = false;
    let _needsUpdateHeader = false;

    function mRenderGroupedList() {
      _needsRender = true;
      _scheduleRender();
    }

    function updateHeader() {
      _needsUpdateHeader = true;
      _scheduleRender();
    }

    function _scheduleRender() {
      if (_renderTimer) return;
      _renderTimer = requestAnimationFrame(() => {
        _renderTimer = null;
        if (_needsRender) {
          _needsRender = false;
          _doRenderGroupedList();
        }
        if (_needsUpdateHeader) {
          _needsUpdateHeader = false;
          _doUpdateHeader();
        }
      });
    }

    function _doUpdateHeader() {
      const valid = data.filter(d => !d.isLoading && d.status);
      const pending = valid.filter(s => s.status.needed > 0).length;
      const critical = valid.filter(s => s.status.is_critical).length;
      const passed = valid.filter(s => s.status.status === 'Aprovado').length;
      // desktop
      const tr = document.getElementById('totalResume');
      if (tr) {
        tr.innerHTML = `${passed} concluídas • ${pending} pendentes • <span style="color:var(--danger)">${critical} críticas</span>`;
      }
      // mobile status line update (if any future element exists)
      // alerta crítico mobile
      mUpdateAlert(critical, valid);
    }

    function mUpdateAlert(criticalCount, valid) {
      const strip = document.getElementById('m-alert-strip');
      if (!strip) return;
      // A questionnaire warning is a session-wide, actionable state — never let a
      // tab switch or grade refresh silently clear it.
      if (strip.dataset.mode === 'questionnaire') return;
      const viewList = document.getElementById('view-list');
      const isListActive = viewList && viewList.classList.contains('active');
      if (criticalCount > 0 && isListActive) {
        const critNames = valid.filter(s => s.status.is_critical).map(s => escapeHtml(s.name)).join(', ');
        strip.innerHTML = `⚠ ${criticalCount} disciplina(s) em situação crítica: <strong>${critNames}</strong>`;
        strip.dataset.mode = 'critical';
        strip.classList.add('visible');
      } else {
        strip.classList.remove('visible');
        delete strip.dataset.mode;
      }
    }





    function _doRenderGroupedList() {
      // Select the main list view section
      const viewList = document.getElementById('view-list');
      if (!viewList) return;

      // Remove existing groups to re-render
      viewList.querySelectorAll('.m-group').forEach(g => g.remove());

      const emptyMsg = document.getElementById('empty-list-msg');
      const freqBtn = document.getElementById('m-nav-frequency');
      
      if (data.length === 0 && !isHistoryMode) {
          if (emptyMsg) {
              emptyMsg.innerHTML = "Opa, você não está em nenhuma turma";
              emptyMsg.style.display = 'block';
          }
          if (freqBtn) {
              freqBtn.style.pointerEvents = 'none';
              freqBtn.style.opacity = '0.3';
          }
          return;
      } else {
          if (emptyMsg) emptyMsg.style.display = 'none';
          if (freqBtn) {
              freqBtn.style.pointerEvents = 'auto';
              freqBtn.style.opacity = '1';
          }
      }

      const sorted = [...data].sort((a, b) => {
        if (a.isLoading && !b.isLoading) return 1;
        if (!a.isLoading && b.isLoading) return -1;
        if (!a.status || !b.status) return 0;
        if (a.status.is_critical && !b.status.is_critical) return -1;
        if (b.status.is_critical && !a.status.is_critical) return 1;
        return b.status.needed - a.status.needed;
      });

      // Priority order (crítica > pendente > em andamento > aprovada > outras) is kept,
      // but all cards now flow into a single grid instead of one row per category.
      const priorityFilters = [
        d => d.status && d.status.is_critical,
        d => d.status && !d.status.is_critical && d.status.needed > 0,
        d => d.status && d.status.status === 'Cursando' && !d.status.is_critical && !(d.status.needed > 0),
        d => d.status && (d.status.status === 'Aprovado' || d.status.status === 'Concluído')
      ];

      const loadingItems = sorted.filter(d => d.isLoading);
      const nonLoading = sorted.filter(d => !d.isLoading);
      const bucketed = new Set();
      const ordered = [...loadingItems];
      priorityFilters.forEach(filter => {
        nonLoading.forEach(item => {
          if (!bucketed.has(item) && filter(item)) {
            bucketed.add(item);
            ordered.push(item);
          }
        });
      });
      nonLoading.forEach(item => { if (!bucketed.has(item)) ordered.push(item); });

      viewList.appendChild(buildMGroup(ordered));
      
      // Atualizar abas secundárias se estiverem ativas durante a chegada de dados em tempo real
      if (document.getElementById('view-stats') && document.getElementById('view-stats').classList.contains('active')) {
          renderChart();
          if (typeof loadAcademicProfile === 'function') loadAcademicProfile();
      }
      if (document.getElementById('view-achievements') && document.getElementById('view-achievements').classList.contains('active')) {
          renderAchievements();
      }
    }

    function buildMGroup(items) {
      const grp = document.createElement('div');
      grp.className = 'm-group';
      const list = document.createElement('div');
      list.className = 'm-group-list';
      items.forEach(item => {
        const el = document.createElement('div');
        el.className = 'm-item';
        if (item.isRefreshing) el.classList.add('refreshing');
        if (!item.isLoading) el.onclick = () => openModal(item.id);
        if (item.isLoading) {
          el.classList.add('skeleton-item');
          el.innerHTML = `<div class="m-item-bar" style="background:var(--text-muted); opacity:.3"></div><div class="m-item-body"><div class="m-item-name">${escapeHtml(item.name)}</div><div class="m-item-sub">Carregando...</div></div><div class="m-item-right"><div class="m-item-score" style="color:var(--text-muted)">-</div><div class="m-item-score-lbl">Média</div></div>`;
        } else {
          const st = item.status || {};
          const barColor = st.is_critical ? 'var(--danger)' : (st.status === 'Aprovado' ? 'var(--success)' : (st.needed > 0 ? 'var(--warning)' : 'var(--accent)'));
          const scoreColor = st.is_critical ? 'var(--danger)' : (st.status === 'Aprovado' ? 'var(--success)' : (st.needed > 0 ? 'var(--warning)' : 'var(--text-main)'));
          let scoreVal = st.average !== undefined ? st.average.toFixed(1) : '-';
          
          let calcMsg = st.message && st.message !== "Concluído" ? st.message : "";
          let subInfo = calcMsg || item.obs || '';
          
          if (item.professor && item.professor !== "Desconhecido") {
              subInfo += ` • Prof. ${escapeHtml(formatProfName(item.professor))}`;
          }
          let detailBadges = '';
          if (st.details) {
            const styling = st.details.styling || {};
            const orderedKeys = ['b1', 'b2', 'r1', 'b3', 'b4', 'r2', 'av1', 'av2', 'reav', 'final', 'nf'];
            Object.keys(st.details).filter(k => typeof st.details[k] === 'number').sort((a, b) => {
              const idxA = orderedKeys.indexOf(a.toLowerCase());
              const idxB = orderedKeys.indexOf(b.toLowerCase());
              const valA = idxA === -1 ? 99 : idxA;
              const valB = idxB === -1 ? 99 : idxB;
              return valA - valB;
            }).forEach(k => {
              const badgeClass = styling[`${k}_class`] || 'bd-info';
              let bg = 'rgba(255, 255, 255, 0.05)', txt = 'var(--text-muted)';
              if (badgeClass === 'bd-ok') { txt = 'var(--success)'; }
              else if (badgeClass === 'bd-danger') { txt = 'var(--danger)'; }
              else if (badgeClass === 'bd-warn') { txt = 'var(--warning)'; }
              detailBadges += `<span class="m-badge" style="background:${bg};color:${txt};border:1px solid rgba(255,255,255,0.05);">${k.toUpperCase()}: ${st.details[k].toFixed(1)}</span>`;
            });
          }
          let neededInfo = st.is_critical ? `<div class="m-item-needed" style="color:var(--danger)">Reprovado</div>` : (st.needed > 0 ? `<div class="m-item-needed" style="color:var(--warning)">Falta ${st.needed.toFixed(1)}</div>` : '');
          el.innerHTML = `<div class="m-item-bar" style="background:${barColor}"></div><div class="m-item-body"><div class="m-item-name">${item.isNew ? '<span class="tag-new">NOVO</span> ' : ''}${escapeHtml(item.name)}</div><div class="m-item-sub">${escapeHtml(subInfo)}</div><div class="m-item-badges">${detailBadges}</div></div><div class="m-item-right"><div class="m-item-score" style="color:${scoreColor}">${scoreVal}</div><div class="m-item-score-lbl">Média</div>${neededInfo}</div>`;
        }
        list.appendChild(el);
      });
      grp.appendChild(list);
      return grp;
    }


    async function refreshCourse(event, id) {
      event.stopPropagation();
      const btn = event.currentTarget;
      if (btn.classList.contains('loading')) return;
      const idx = data.findIndex(d => String(d.id) === String(id));
      if (idx !== -1) { data[idx].isRefreshing = true; mRenderGroupedList(); }
      try {
        const resp = await fetch(`/api/update_course/${id}`, {
          method: 'POST', headers: { 'X-CSRFToken': window.APP_CONFIG.csrfToken }
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(JSON.stringify(errData || {}));
        }
        const result = await resp.json();
        const i = data.findIndex(d => String(d.id) === String(result.id));
        if (i !== -1) {
          const oldData = data[i];
          const isNew = oldData.grades ? !deepEqual(oldData.grades, result.data.grades) : true;
          data[i] = { ...oldData, ...result.data, id: String(result.data.id || result.id), isNew: isNew, isRefreshing: false };
          const li = liveData.findIndex(d => String(d.id) === String(result.id));
          if (li !== -1) liveData[li] = data[i];
          if (result.frequency) data[i].frequency = result.frequency;
          saveGradesState();
          mRenderGroupedList();
          updateHeader();
          if (document.getElementById('view-frequency').classList.contains('active')) renderFrequency();
        }
      } catch (e) {
        console.error(e);
        let erroMsg = "Falha ao atualizar disciplina.";
        try {
          const j = JSON.parse(e.message);
          if (j.is_questionnaire) {
            erroMsg = j.error;
            const strip = document.getElementById('m-alert-strip');
            if (strip) {
              strip.innerHTML = `⚠️ <strong>Atenção:</strong> ${escapeHtml(erroMsg)}`;
              strip.style.background = 'rgba(250,204,21,0.1)';
              strip.style.borderLeftColor = '#facc15';
              strip.style.color = '#facc15';
              strip.dataset.mode = 'questionnaire';
              strip.classList.add('visible');
            }
          } else if (j.error) erroMsg = j.error;
        } catch (ex) { }
        alert(erroMsg);
        const idx2 = data.findIndex(d => String(d.id) === String(id));
        if (idx2 !== -1) { data[idx2].isRefreshing = false; mRenderGroupedList(); }
      }
    }





    function formatFreqMetric(value, perSession, showFraction = false) {
      if (!perSession || perSession <= 1) {
        return `${value}`;
      }
      const days = Math.floor(value / perSession);
      if (showFraction) {
        return `${days} (${value}/${perSession})`;
      } else {
        return `${days}`;
      }
    }

    function _bindFrequencyHandlers(container) {
      if (container._freqBound) return;
      container._freqBound = true;
      container.addEventListener('click', (event) => {
        const toggle = event.target.closest('[data-freq-toggle]');
        if (toggle) { toggleFreqDetails(toggle.dataset.freqToggle); return; }
        const help = event.target.closest('[data-freq-help]');
        if (help) {
          const d = help.dataset;
          showFreqHelp(d.fhName, Number(d.fhTf), Number(d.fhMf), Number(d.fhP),
                       Number(d.fhNr), Number(d.fhAf), Number(d.fhPs), event);
        }
      });
    }

    function renderFrequency() {
      const container = document.getElementById('frequency-container');
      _bindFrequencyHandlers(container);
      container.innerHTML = '';

      if (isHistoryMode) {
        container.innerHTML = `
        <div style="text-align:center; padding:40px 20px; color:var(--text-muted);">
          <div style="font-size:48px; margin-bottom:16px;">📅</div>
          <div style="font-weight:700; color:#fff; margin-bottom:8px;">Frequência Indisponível</div>
          <p style="font-size:13px; opacity:0.7;">Por limitações do SIGAA, a frequência detalhada só pode ser visualizada no semestre atual.</p>
          <button onclick="switchSemesterM('Atual')" style="margin-top:20px; background:var(--accent); color:#fff; border:none; padding:10px 20px; border-radius:12px; font-weight:700; cursor:pointer;">
            Voltar para Semestre Atual
          </button>
        </div>
      `;
        return;
      }

      const items = data.filter(d => !d.isLoading);
      const itemsWithFreq = items.map(d => {
        if (!d.frequency || d.frequency.nao_lancada) {
          const max_faltas = (d.frequency && d.frequency.max_faltas) || 18;
          const aulas_total = (d.frequency && d.frequency.aulas_total) || 72;
          return { ...d, frequency: { total_faltas: 0, max_faltas: max_faltas, percent: 0, aulas_total: aulas_total, nao_lancada: true } };
        }
        return d;
      });
      
      let overallAvg = 0, sumTotalFaltas = 0, sumMaxFaltas = 0, sumTotalAulas = 0;
      let critCount = 0;
      let totalDiscs = itemsWithFreq.length;
      
      if (totalDiscs > 0) {
        overallAvg = itemsWithFreq.reduce((s, d) => s + (d.frequency.percent || 0), 0) / totalDiscs;
        sumTotalFaltas = itemsWithFreq.reduce((s, d) => s + (d.frequency.total_faltas || 0), 0);
        sumMaxFaltas = itemsWithFreq.reduce((s, d) => s + (d.frequency.max_faltas || 18), 0);
        sumTotalAulas = itemsWithFreq.reduce((s, d) => s + (d.frequency.aulas_total || ((d.frequency.max_faltas || 18) * 4)), 0);
        critCount = itemsWithFreq.filter(d => ((d.frequency.max_faltas || 18) - (d.frequency.total_faltas || 0)) <= 1).length;
      }
      
      const presencaPercent = sumTotalAulas > 0 ? Math.max(0, 100 - (sumTotalFaltas / sumTotalAulas * 100)).toFixed(1) : 100;

      const statGrid = document.createElement('div');
      statGrid.className = 'stat-grid';
      statGrid.innerHTML = `
        <div class="stat-box"><div class="stat-val" style="color:#fff">${totalDiscs}</div><div class="stat-lbl">Matérias</div></div>
        <div class="stat-box"><div class="stat-val" style="color:var(--danger)">${critCount}</div><div class="stat-lbl">Críticas</div></div>
        <div class="stat-box"><div class="stat-val" style="color:var(--safe)">${Math.max(0, sumMaxFaltas - sumTotalFaltas)}</div><div class="stat-lbl">Restantes Totais</div></div>
        <div class="stat-box"><div class="stat-val" style="color:#00ffff">${presencaPercent}%</div><div class="stat-lbl">Presença Geral</div></div>
      `;
      container.appendChild(statGrid);

      if (critCount > 0) {
        const critDiscs = itemsWithFreq.filter(d => (d.frequency.max_faltas - d.frequency.total_faltas) <= 1);
        const critNames = critDiscs.map(d => `<b>${escapeHtml(d.name.substring(0,25))}</b>`).join(', ');
        const banner = document.createElement('div');
        banner.className = 'freq-banner';
        banner.innerHTML = `⚠️ <span>${critNames} com faltas no limite!</span>`;
        container.appendChild(banner);
      }
      
      const secTitle = document.createElement('div');
      secTitle.className = 'freq-sec-title';
      secTitle.innerText = 'Disciplinas · Ordenado por urgência';
      container.appendChild(secTitle);

      const listContainer = document.createElement('div');
      listContainer.className = 'freq-grid';
      container.appendChild(listContainer);

      const sortedItems = [...items].sort((a, b) => {
        const getRem = (item) => {
          if (!item.frequency || item.frequency.nao_lancada) return 18;
          return item.frequency.max_faltas - item.frequency.total_faltas;
        };
        return getRem(a) - getRem(b);
      });

      sortedItems.forEach(item => {
        const div = document.createElement('div');
        
        const total_faltas = (item.frequency && item.frequency.total_faltas) || 0;
        const max_faltas = (item.frequency && item.frequency.max_faltas) || 18;
        const presencas = (item.frequency && item.frequency.presencas) || 0;
        const aulas_per_session = (item.frequency && item.frequency.aulas_per_session) || 4;
        
        const daysTotalFaltas = Math.floor(total_faltas / aulas_per_session);
        const daysMaxFaltas = Math.floor(max_faltas / aulas_per_session);
        const daysPresencas = Math.floor(presencas / aulas_per_session);
        const daysRemaining = Math.max(0, daysMaxFaltas - daysTotalFaltas);

        const remaining = Math.max(0, max_faltas - total_faltas);
        const aulas_total = (item.frequency && item.frequency.aulas_total) || (max_faltas * 4);
        const pct = Math.min(100, (total_faltas / (max_faltas || 1)) * 100);
        
        let badgeClass = 'freq-b-safe';
        let strokeColor = '#34d399';
        let isCrit = false;
        
        if (remaining <= 1 || pct >= 75) { badgeClass = 'freq-b-crit'; strokeColor = '#f43f5e'; isCrit = true; }
        else if (remaining <= 3 || pct >= 50) { badgeClass = 'freq-b-warn'; strokeColor = '#fbbf24'; }

        div.className = 'freq-item' + (isCrit ? ' crit open' : '');
        div.onclick = function(e) { 
          if(e.target.closest('.freq-date-chip')) return;
          this.classList.toggle('open'); 
        };

        const circumference = 100.5;
        const offset = circumference - (circumference * pct / 100);

        let chipsHtml = '';
        if (item.frequency.logs && item.frequency.logs.length > 0) {
          const faltasLogs = item.frequency.logs.filter(l => l.status === 'Ausente');
          if (faltasLogs.length > 0) {
            chipsHtml = faltasLogs.map(l => `<span class="freq-date-chip">${l.date}</span>`).join('');
          } else {
            chipsHtml = `<span style="font-size:11px; color:var(--text-muted)">Sem datas específicas registradas.</span>`;
          }
        } else {
          chipsHtml = `<span style="font-size:11px; color:var(--text-muted)">Histórico de datas indisponível.</span>`;
        }

        div.innerHTML = `
          <div class="freq-item-head">
            <div class="freq-ring">
              <svg viewBox="0 0 40 40">
                <circle class="bg" cx="20" cy="20" r="16"/>
                <circle class="fg" cx="20" cy="20" r="16" stroke="${strokeColor}" stroke-dasharray="100.5" stroke-dashoffset="${offset}"/>
              </svg>
              <div class="freq-ring-label">${Math.round(pct)}%</div>
            </div>
            <div class="freq-item-info">
              <div class="freq-item-subject">${escapeHtml(item.name)}</div>
              <div class="freq-item-meta">${total_faltas} de ${max_faltas} faltas permitidas</div>
            </div>
            <div class="freq-item-badge ${badgeClass}">${daysRemaining} dia${daysRemaining !== 1 ? 's' : ''} restante${daysRemaining !== 1 ? 's' : ''}</div>
            <div class="freq-chevron">▾</div>
          </div>
          <div class="freq-item-body">
            <div class="freq-item-body-inner">
              <div class="freq-body-row"><span>Presenças</span><span>${daysPresencas} dias (${presencas} aulas)</span></div>
              <div class="freq-body-row"><span>Limite da disciplina</span><span>${daysMaxFaltas} dias (${max_faltas} faltas)</span></div>
              <div class="freq-body-row"><span>Faltas registradas</span><span>${daysTotalFaltas} dias (${total_faltas} faltas)</span></div>
              <div class="freq-dates-row" style="margin-top:8px;">${chipsHtml}</div>
            </div>
          </div>
        `;
        listContainer.appendChild(div);
      });
    }
    
    function renderAbsencesChart() {
      if (typeof Chart === 'undefined') return;
      const chartCard = document.getElementById('absences-chart-card');
      const items = data.filter(d => !d.isLoading && d.frequency);
      
      if (items.length === 0) { 
        if (chartCard) chartCard.style.display = 'none'; 
        return; 
      }
      
      if (chartCard) chartCard.style.display = 'block';
      const ctx = document.getElementById('absencesChart').getContext('2d');
      if (absencesChart) absencesChart.destroy();
      
      absencesChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: items.map(d => d.name.substring(0, 10) + '...'),
          datasets: [{ 
            label: 'Faltas', 
            data: items.map(d => (d.frequency && d.frequency.total_faltas) || 0), 
            borderColor: '#f43f5e', 
            backgroundColor: 'rgba(244,63,94,0.2)', 
            fill: true, 
            tension: 0.3 
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
            x: { ticks: { color: '#999', font: { size: 10 } }, grid: { display: false } }
          }
        }
      });
    }

    function renderChart() {
      if (typeof Chart === 'undefined') return; // chart.js (defer) ainda não carregou
      
      // Renderiza faltas independentemente das notas
      renderAbsencesChart();
      
      const chartCard = document.getElementById('chart-card');
      const active = data.filter(d => !d.isLoading && d.status && d.status.needed > 0)
        .sort((a, b) => b.status.needed - a.status.needed).slice(0, 10);
      if (active.length === 0) { chartCard.style.display = 'none'; return; }
      chartCard.style.display = 'block';
      const ctx = document.getElementById('chartCanvas').getContext('2d');
      if (chart) chart.destroy();
      chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: active.map(d => d.name.substring(0, 8)),
          datasets: [{ label: 'Falta', data: active.map(d => d.status.needed), backgroundColor: active.map(d => d.status.is_critical ? '#ef4444' : '#38bdf8'), borderRadius: 4 }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
            x: { ticks: { color: '#999', font: { size: 10 } }, grid: { display: false } }
          }
        }
      });
    }


    async function loadAcademicProfile(force = false) {
      const loading = document.getElementById('academic-profile-loading');
      const content = document.getElementById('academic-profile-content');
      if (profileData && Object.keys(profileData.history_raw || {}).length > 0 && !force) { renderAcademicProfileData(); content.style.display = 'block'; loading.style.display = 'none'; return; }
      const isDemo = window.location.pathname === '/demo';
      if (!profileData) { loading.style.display = 'block'; content.style.display = 'none'; }
      else { const btn = document.getElementById('btn-force-update'); if (btn) { btn.disabled = true; btn.textContent = 'Atualizando...'; } }
      try {
        if (isDemo) {
          await new Promise(r => setTimeout(r, 800));
          profileData = { general_average: 8.7, best_grade: 10.0, best_subject: "Programação Web", semesters: [{ semester: "2023.1", average: 7.5, count: 5 }, { semester: "2023.2", average: 8.2, count: 5 }, { semester: "2024.1", average: 8.5, count: 6 }], history_raw: {} };
        } else {
          const resp = await fetch(force ? '/api/academic_profile?force=true' : '/api/academic_profile');
          if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            if (errData.is_questionnaire) {
              const strip = document.getElementById('m-alert-strip');
              if (strip) {
                strip.innerHTML = `⚠️ <strong>Atenção:</strong> ${escapeHtml(errData.error)}`;
                strip.style.background = 'rgba(250,204,21,0.1)';
                strip.style.borderLeftColor = '#facc15';
                strip.style.color = '#facc15';
                strip.dataset.mode = 'questionnaire';
                strip.classList.add('visible');
              }
            }
            throw new Error(errData.error || "Failed");
          }
          profileData = await resp.json();
        }

        if (profileData && profileData.history_raw) {
          const liveCourseNames = liveData.filter(d => !d.isLoading).map(d => d.name.toLowerCase().trim());
          let overlapSem = null;
          for (const [sem, courses] of Object.entries(profileData.history_raw)) {
            const histNames = courses.map(c => c.name.toLowerCase().trim());
            const overlap = histNames.filter(n => liveCourseNames.some(ln => ln.includes(n) || n.includes(ln)));
            
            const hasFinalStatus = courses.some(c => {
              const st = (c.status || '').toLowerCase();
              return st.includes('aprovado') || st.includes('reprovado') || st.includes('concluído') || 
                     st.includes('cancelado') || st.includes('dispensado') || st.includes('trancado');
            });

            if (overlap.length > 0 && !hasFinalStatus) {
              overlapSem = sem;
            }
          }
          if (overlapSem) {
            delete profileData.history_raw[overlapSem];
            profileData.semesters = profileData.semesters.filter(s => s.semester !== overlapSem);
          }
        }

        // populate dropdowns
        const populateSems = (dropdownEl, contentEl) => {
          if (!dropdownEl || !contentEl || !profileData.history_raw) return;

          dropdownEl.style.display = 'inline-block';
          contentEl.innerHTML = '<button onclick="switchSemester(\'Atual\')">Atual</button>';
          profileData.semesters.map(s => s.semester).sort().reverse().forEach(sem => {
            if (!sem.includes('(Atual)')) {
              const semBtn = document.createElement('button');
              semBtn.textContent = sem;
              semBtn.addEventListener('click', () => switchSemester(sem));
              contentEl.appendChild(semBtn);
            }
          });
        };
        populateSems(document.getElementById('semDropdown'), document.getElementById('semDropdownContent'));
        _buildMSemDropdown();
        renderAcademicProfileData();
        if (typeof isHistoryMode !== 'undefined' && isHistoryMode) {
          const lbl = document.getElementById('currentSemesterLabel-m') || document.getElementById('currentSemesterLabel');
          if (lbl && lbl.textContent && lbl.textContent !== 'Atual') {
            _doSwitchSemester(lbl.textContent, lbl);
          }
        }
        loading.style.display = 'none'; content.style.display = 'block';
      } catch (e) {
        console.error(e); loading.textContent = "Não foi possível carregar o histórico completo.";
      } finally {
        const btn = document.getElementById('btn-force-update');
        if (btn) { btn.disabled = false; btn.textContent = '↻ Atualizar Histórico'; }
      }
    }

    function renderAcademicProfileData() {
      if (!profileData) return;
      document.getElementById('prof-general-avg').textContent = profileData.general_average;
      document.getElementById('prof-best-grade').textContent = profileData.best_grade;
      document.getElementById('prof-best-subj').textContent = profileData.best_subject;
      let finalSemesters = [...profileData.semesters];
      const currentGrades = liveData.filter(d => !d.isLoading && d.status);
      if (currentGrades.length > 0) {
        const currentAvgs = currentGrades.map(d => d.status.average || 0);
        const currentAvg = currentAvgs.length > 0 ? (currentAvgs.reduce((a, b) => a + b, 0) / currentAvgs.length) : 0;
        const now = new Date();
        const currentLabel = `${now.getFullYear()}.${now.getMonth() < 6 ? '1' : '2'} (Atual)`;
        if (!finalSemesters.find(s => s.semester.startsWith(currentLabel.split(' ')[0]))) {
          finalSemesters.push({ semester: currentLabel, average: parseFloat(currentAvg.toFixed(2)), count: currentAvgs.length });
        }
      }
      renderHistoryChart(finalSemesters);
    }

    function forceUpdateProfile() {
      if (confirm("Deseja forçar a atualização do histórico? Isso pode demorar alguns segundos.")) loadAcademicProfile(true);
    }


    function switchSemester(sem) {
      const lbl = document.getElementById('currentSemesterLabel');
      _doSwitchSemester(sem, lbl);
    }

    function _buildMSemDropdown(activeSem) {
      const mDrop = document.getElementById('semDropdown-m');
      const mContent = document.getElementById('semDropdownContent-m');
      if (!mDrop || !mContent || !profileData || !profileData.history_raw) return;
      mDrop.style.display = 'inline-block';
      const current = activeSem || 'Atual';
      mContent.innerHTML = '';
      const atualBtn = document.createElement('button');
      atualBtn.textContent = 'Atual';
      atualBtn.className = current === 'Atual' ? 'sem-active' : '';
      atualBtn.addEventListener('click', () => switchSemesterM('Atual'));
      mContent.appendChild(atualBtn);
      profileData.semesters.map(s => s.semester).sort().reverse().forEach(sem => {
        if (!sem.includes('(Atual)')) {
          const btn = document.createElement('button');
          btn.textContent = sem;
          btn.className = current === sem ? 'sem-active' : '';
          btn.addEventListener('click', () => switchSemesterM(sem));
          mContent.appendChild(btn);
        }
      });
    }

    function switchSemesterM(sem) {
      const lbl = document.getElementById('currentSemesterLabel-m');
      _doSwitchSemester(sem, lbl);
      const lblD = document.getElementById('currentSemesterLabel');
      if (lblD) lblD.textContent = sem === 'Atual' ? 'Atual' : sem;
      _buildMSemDropdown(sem);
      document.getElementById('semDropdown-m').classList.remove('show');
    }

    function _doSwitchSemester(sem, labelEl) {
      if (sem === 'Atual') {
        isHistoryMode = false; data = liveData;
        if (labelEl) labelEl.textContent = 'Atual';
        const tr = document.getElementById('totalResume');
        if (tr) tr.textContent = "Visualizando dados em tempo real";
        const st = document.getElementById('m-status-text');
        if (st) {
          st.textContent = '';
          st.classList.remove('visible');
        }
      } else {
        isHistoryMode = true;
        if (labelEl) labelEl.textContent = sem;
        if (profileData && profileData.history_raw && profileData.history_raw[sem]) {
          const rawList = profileData.history_raw[sem];
          data = rawList.map((subj, index) => {
            let details = {};
            if (subj.grades) subj.grades.forEach(g => { details[g.name] = g.value; });
            
            let normalizedStatus = 'Indefinido';
            let isCritical = false;
            let finalAvg = subj.final_grade !== null ? subj.final_grade : 0.0;
            let message = subj.status;
            let needed = 0;
            
            if (subj.status_dict) {
                const st = subj.status_dict;
                isCritical = st.is_critical;
                normalizedStatus = (st.status === 'APPROVED' || st.status === 'Aprovado') ? 'Aprovado' : ((st.status === 'FAILED' || st.status === 'Reprovado') ? 'Reprovado' : subj.status);
                message = st.message || subj.status;
                needed = st.needed || 0;
                if (st.details) details = st.details;
                finalAvg = st.average !== undefined ? st.average : finalAvg;
            } else {
                // Normalize status from SIGAA bulletin (Portuguese and uppercase)
                const rawStatus = (subj.status || '').toUpperCase();
                if (rawStatus.includes('APROVADO') || rawStatus.includes('CONCLUÍDO')) {
                  normalizedStatus = 'Aprovado';
                } else if (rawStatus.includes('REPROVADO')) {
                  normalizedStatus = 'Reprovado';
                  isCritical = true;
                } else if (rawStatus.includes('CURSANDO')) {
                  normalizedStatus = 'Cursando';
                } else if (rawStatus.includes('FINAL') || rawStatus.includes('PROVA FINAL')) {
                  normalizedStatus = 'Prova Final';
                } else if (rawStatus.includes('RECUPERAC') || rawStatus.includes('RECUPERAÇ')) {
                  normalizedStatus = 'Recuperação';
                } else if (subj.status) {
                  normalizedStatus = subj.status;
                }
            }
            
            return {
              id: 1000 + index, name: subj.name, obs: subj.status, grades: subj.grades || [], professor: subj.professor,
              exigencia_media: subj.exigencia_media,
              status: { status: normalizedStatus, average: finalAvg, needed: needed, is_critical: isCritical, message: message, details: details },
              frequency: { total_faltas: subj.absences || 0, max_faltas: 0, percent: 0 },
              isLoading: false, isRefreshing: false
            };
          });
          const tr = document.getElementById('totalResume');
          if (tr) tr.textContent = `Visualizando histórico: ${sem}`;
          const st = document.getElementById('m-status-text');
          if (st) {
            st.textContent = sem;
            st.classList.add('visible');
          }
        } else {
          data = [];
        }
      }
      
      // Async fetch for course ratings and user_voted status for the newly selected semester
      const pares = [];
      if (typeof data !== 'undefined' && Array.isArray(data)) {
          data.forEach(d => {
              if (d.name && d.professor && d.professor !== 'Desconhecido') {
                  pares.push({disciplina: reviewName(d), professor: d.professor});
              }
          });
      }
      if (pares.length > 0) {
          fetch('/api/avaliacoes/medias_lote', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
              body: JSON.stringify({ pares })
          })
          .then(response => { if (response.ok) return response.json(); throw new Error("Batch fetch failed"); })
          .then(loteData => {
              window.courseRatings = { ...(window.courseRatings || {}), ...(loteData.averages || {}) };
              window.courseUserVoted = { ...(window.courseUserVoted || {}), ...(loteData.user_voted || {}) };
              mRenderGroupedList();
          })
          .catch(e => console.error("Error fetching medias em lote on switch", e));
      }
      
      mRenderGroupedList();
      renderFrequency();
      renderChart();
      renderAchievements();
      updateHeader();
    }


    function renderHistoryChart(semesters) {
      const ctx = document.getElementById('historyChart').getContext('2d');
      if (historyChart) historyChart.destroy();
      const sorted = [...semesters].sort((a, b) => a.semester.localeCompare(b.semester));
      historyChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: sorted.map(s => s.semester),
          datasets: [{ label: 'Média Semestral', data: sorted.map(s => s.average), borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.2)', fill: true, tension: 0.3 }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, max: 10, grid: { color: 'rgba(255,255,255,0.1)' } },
            x: { ticks: { color: '#999' }, grid: { display: false } }
          }
        }
      });
    }


    const RARITY_COLORS = {
      comum: { text: '#b0bec5', bg: 'rgba(176, 190, 197, 0.1)', border: '#78909c', shadow: 'rgba(176,190,197,0.2)' },
      raro: { text: '#42a5f5', bg: 'rgba(66, 165, 245, 0.1)', border: '#1e88e5', shadow: 'rgba(66,165,245,0.4)' },
      epico: { text: '#ab47bc', bg: 'rgba(171, 71, 188, 0.1)', border: '#8e24aa', shadow: 'rgba(171,71,188,0.5)' },
      lendario: { text: '#fbc02d', bg: 'rgba(251, 192, 45, 0.1)', border: '#fbc02d', shadow: 'rgba(251,192,45,0.6)' }
    };
    
    const RARITY_NAMES = {
      comum: 'Comum',
      raro: 'Raro',
      epico: 'Épico',
      lendario: 'Lendário'
    };

    const ACHIEVEMENTS_DB = [
      { id: 'meio_caminho', rarity: 'comum', icon: '', name: 'Meio Caminho Andado', desc: 'Atingir 50% de conclusão do curso', getProgress: (d) => { const pct = (window.__initialProfile && window.__initialProfile.integration_percentage) ? window.__initialProfile.integration_percentage : 0; return { unlocked: pct >= 50, current: Math.min(pct, 50), max: 50 }; } },
      
      { id: 'reta_final', rarity: 'raro', icon: '', name: 'Reta Final', desc: 'Atingir 90% de conclusão do curso', getProgress: (d) => { const pct = (window.__initialProfile && window.__initialProfile.integration_percentage) ? window.__initialProfile.integration_percentage : 0; return { unlocked: pct >= 90, current: Math.min(pct, 90), max: 90 }; } },
      
      { id: 'dever_cumprido', rarity: 'lendario', icon: '', name: 'Dever Cumprido', desc: 'Atingir 100% de conclusão do curso', getProgress: (d) => { const pct = (window.__initialProfile && window.__initialProfile.integration_percentage) ? window.__initialProfile.integration_percentage : 0; return { unlocked: pct >= 100, current: Math.min(pct, 100), max: 100 }; } },
      
      { id: 'primeiro_passo', rarity: 'comum', icon: '', name: 'Primeiro Passo', desc: 'Acessar o painel do aluno pela primeira vez', getProgress: (d) => { return { unlocked: true, current: 1, max: 1 }; } },
      
      { id: 'primeiro_10', rarity: 'comum', icon: '🎯', name: 'Primeiro 10', desc: 'Tirar 10 em qualquer avaliação', getProgress: (d) => { const u = d.some(c => hasGradeVal(c, 10)); return { unlocked: u, current: u?1:0, max: 1 }; } },
      
      { id: 'genio_incompreendido', rarity: 'epico', icon: '🧠', name: 'Gênio Incompreendido', desc: 'Média 9+ em 3 disciplinas no semestre', getProgress: (d) => { 
          const count = d.filter(c => c.status && c.status.average >= 9).length; 
          return { unlocked: count >= 3, current: Math.min(count, 3), max: 3 }; 
      }},
      
      { id: 'sobrevivente', rarity: 'raro', icon: '🔥', name: 'Sobrevivente', desc: 'Passar na recuperação ou prova final', getProgress: (d) => { 
          const v = d.some(c => c.status && c.status.status && (c.status.status.includes('Recuperação') || c.status.status.includes('Prova Final') || (c.status.status.includes('Aprovado') && hasGradeName(c, 'Recuperação'))));
          return { unlocked: !!v, current: v?1:0, max: 1 }; 
      }},
      
      { id: 'onipresente', rarity: 'lendario', icon: '👑', name: 'Onipresente', desc: '100% de presença em todas as disciplinas do semestre', getProgress: (d) => { 
          const count = d.filter(c => c.frequency && c.frequency.percent === 0).length;
          const max = d.length > 0 ? d.length : 1;
          const u = d.length > 0 && count === d.length;
          return { unlocked: u, current: count, max: max }; 
      }},
      
      { id: 'cartola', rarity: 'epico', icon: '🎩', name: 'Cartola do Semestre', desc: 'Média final maior que 8 em todas as disciplinas', getProgress: (d) => { 
          const count = d.filter(c => c.status && c.status.average > 8).length;
          const max = d.length > 0 ? d.length : 1;
          const u = d.length > 0 && count === d.length;
          return { unlocked: u, current: count, max: max }; 
      }},
      
      { id: 'polivalente', rarity: 'raro', icon: '⚔️', name: 'Polivalente', desc: 'Cursar 6 ou mais disciplinas em um único semestre', getProgress: (d) => { 
          const count = d.length; 
          return { unlocked: count >= 6, current: Math.min(count, 6), max: 6 }; 
      }},
      
      { id: 'quase_la', rarity: 'comum', icon: '😅', name: 'Na Trave', desc: 'Passar com média igual a 5 ou 7 exatos (nota de corte)', getProgress: (d) => { 
          const u = d.some(c => c.status && (c.status.average === 5 || c.status.average === 7) && c.status.status && c.status.status.includes('Aprovado'));
          return { unlocked: !!u, current: u?1:0, max: 1 }; 
      }}
    ];

    function hasGradeVal(course, val) {
      if (!course.grades) return false;
      const check = (list) => { for (let g of list) { if (g.value === val) return true; if (g.grades) if (check(g.grades)) return true; } return false; };
      return check(course.grades);
    }

    function hasGradeName(course, nameChunk) {
      if (!course.grades) return false;
      const check = (list) => { for (let g of list) { if (g.name && g.name.toLowerCase().includes(nameChunk.toLowerCase())) return true; if (g.grades) if (check(g.grades)) return true; } return false; };
      return check(course.grades);
    }

    let claimedAchievements = window.__initialProfile && window.__initialProfile.claimed_achievements ? window.__initialProfile.claimed_achievements : [];

    window.claimAchievement = async function(id) {
      const btn = document.getElementById(`claim-btn-${id}`);
      if (btn) {
          btn.disabled = true;
          btn.innerHTML = 'Reivindicando...';
          btn.style.opacity = '0.7';
      }
      try {
          const resp = await fetch('/api/achievements/claim', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
              body: JSON.stringify({ achievement_id: id })
          });
          const resData = await resp.json();
          if (resp.ok && resData.success) {
              claimedAchievements.push(id);
              renderAchievements();
          } else {
              alert(resData.error || 'Erro ao reivindicar conquista.');
              if (btn) { btn.disabled = false; btn.innerHTML = 'Reivindicar Título'; btn.style.opacity = '1'; }
          }
      } catch (e) {
          alert('Falha de rede.');
          if (btn) { btn.disabled = false; btn.innerHTML = 'Reivindicar Título'; btn.style.opacity = '1'; }
      }
    };

    function renderAchievements() {
      const list = document.getElementById('achievements-list');
      const statsContainer = document.getElementById('achievements-stats');
      if (!list || !statsContainer) return;
      list.innerHTML = '';
      statsContainer.innerHTML = '';
      
      const validData = data.filter(d => !d.isLoading);
      const achs = ACHIEVEMENTS_DB.map(ach => ({ ...ach, state: ach.getProgress(validData) }));
      achs.sort((a, b) => {
        const aUnlocked = a.state.unlocked ? 1 : 0;
        const bUnlocked = b.state.unlocked ? 1 : 0;
        
        if (aUnlocked !== bUnlocked) return bUnlocked - aUnlocked;
        
        if (!a.state.unlocked && !b.state.unlocked) {
            const pctA = a.state.max > 0 ? (a.state.current / a.state.max) : 0;
            const pctB = b.state.max > 0 ? (b.state.current / b.state.max) : 0;
            if (pctA !== pctB) return pctB - pctA;
        }
        
        return a.rarity.localeCompare(b.rarity);
      });
      
      let unlockedCount = 0;
      let rarityCounts = { comum: 0, raro: 0, epico: 0, lendario: 0 };
      
      achs.forEach(a => {
        if (claimedAchievements.includes(a.id)) {
           unlockedCount++;
           if (rarityCounts[a.rarity] !== undefined) rarityCounts[a.rarity]++;
        }
      });
      
      statsContainer.innerHTML = `
        <div style="background: var(--bg-lighter); padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid var(--border); color: var(--text-main);">
          ${unlockedCount}/${achs.length} Títulos Obtidos
        </div>
        ${rarityCounts.lendario > 0 ? `<div style="background: ${RARITY_COLORS.lendario.bg}; color: ${RARITY_COLORS.lendario.text}; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid ${RARITY_COLORS.lendario.border}; box-shadow: 0 0 8px ${RARITY_COLORS.lendario.shadow};">${rarityCounts.lendario} Lendárias</div>` : ''}
        ${rarityCounts.epico > 0 ? `<div style="background: ${RARITY_COLORS.epico.bg}; color: ${RARITY_COLORS.epico.text}; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid ${RARITY_COLORS.epico.border};">${rarityCounts.epico} Épicas</div>` : ''}
        ${rarityCounts.raro > 0 ? `<div style="background: ${RARITY_COLORS.raro.bg}; color: ${RARITY_COLORS.raro.text}; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid ${RARITY_COLORS.raro.border};">${rarityCounts.raro} Raras</div>` : ''}
      `;

      const RIBBON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="8" r="6"/><path d="M8.5 13.2 6 21l6-3 6 3-2.5-7.8"/></svg>`;

      achs.forEach(a => {
        const div = document.createElement('div');
        const isCompleted = a.state.unlocked;
        const isClaimed = claimedAchievements.includes(a.id);
        const rColor = RARITY_COLORS[a.rarity];
        
        div.className = 'diploma ' + (isClaimed ? 'unlocked' : 'locked');
        
        if (isClaimed) {
          div.style.setProperty('--accent', rColor.border);
          if (a.rarity === 'lendario' || a.rarity === 'epico') {
             div.style.boxShadow = `0 4px 24px ${rColor.shadow}`;
          }
        } else if (isCompleted) {
          // Destaca ligeiramente conquistas prontas para reivindicar
          div.style.opacity = '1';
          div.style.borderColor = rColor.border;
          div.style.boxShadow = `0 0 12px ${rColor.shadow}`;
        } else if (a.state.current > 0) {
          // Em progresso: brilho da cor da raridade proporcional ao avanço
          const p = a.state.current / a.state.max;
          div.style.borderColor = rColor.border;
          div.style.boxShadow = `0 0 ${2 + (p * 8)}px ${rColor.shadow}`;
          div.style.opacity = (0.5 + (p * 0.4)).toFixed(2);
        }
        
        const pct = (a.state.current / a.state.max) * 100;
        const userName = window.APP_CONFIG && window.APP_CONFIG.currentUser ? window.APP_CONFIG.currentUser : 'Você';
        
        if (isClaimed) {
          div.innerHTML += `<div style="position:absolute; top:0; left:0; width:100%; height:100%; background: radial-gradient(circle at center, ${rColor.bg} 0%, transparent 70%); pointer-events:none; z-index:0;"></div>`;
        }

        let footHtml = '';
        if (isClaimed) {
           footHtml = `
          <div style="width:100%; display:flex; justify-content:space-between; margin-bottom:4px;">
            <span>OBTIDO</span>
            <span>${a.state.current}/${a.state.max}</span>
          </div>
          <div style="width:100%; height:4px; background:var(--bg-lighter); border-radius:2px; overflow:hidden;">
            <div style="height:100%; width:100%; background:${rColor.border};"></div>
          </div>`;
        } else if (isCompleted) {
           footHtml = `
          <button id="claim-btn-${a.id}" onclick="claimAchievement('${a.id}')" style="width: 100%; background: ${rColor.border}; color: ${a.rarity === 'lendario' ? '#000' : '#fff'}; border: none; padding: 10px; border-radius: 4px; font-weight: bold; cursor: pointer; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; box-shadow: 0 2px 8px ${rColor.shadow}; transition: transform 0.2s;">
            Reivindicar Título
          </button>`;
        } else {
           footHtml = `
          <div style="width:100%; display:flex; justify-content:space-between; margin-bottom:4px;">
            <span>EM PROGRESSO</span>
            <span>${a.state.current}/${a.state.max}</span>
          </div>
          <div style="width:100%; height:4px; background:var(--bg-lighter); border-radius:2px; overflow:hidden;">
            <div style="height:100%; width:${pct}%; background:${rColor.border}; opacity: 0.8; transition:width 1s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 0 8px ${rColor.shadow};"></div>
          </div>`;
        }

        div.innerHTML += `
          <span class="c2"></span>
          <span class="diploma-ribbon" style="position:relative; z-index:1;">${RIBBON}</span>
          <span class="kicker" style="position:relative; z-index:1; ${isClaimed ? 'color:' + rColor.border : ''}">
            ${RARITY_NAMES[a.rarity]}
            <span style="display:block; margin-top:6px; font-size:0.9em; opacity:0.8; letter-spacing:0.5px;">
              ${isClaimed ? 'OUTORGADO A ' + userName.toUpperCase() : 'NÃO CONCEDIDO'}
            </span>
          </span>
          <h3 style="position:relative; z-index:1;">${a.name}</h3>
          <p class="crit" style="position:relative; z-index:1;">${a.desc}</p>
          <div class="foot" style="position:relative; z-index:1; display:flex; flex-direction:column; align-items:center; gap:6px;">
            ${footHtml}
          </div>
        `;
        
        list.appendChild(div);
      });
    }


    function getStatusColor(status) {
      if (status === 'Aprovado' || status === 'Concluído') return 'bd-ok';
      if (status === 'Reprovado') return 'bd-danger';
      if (status === 'Cursando' || status === 'Indefinido') return 'bd-info';
      return 'bd-warn';
    }


    function openModal(id = null) {
      const modal = document.getElementById('modal');
      modal.style.display = 'flex';
      if (id) {
        const item = data.find(d => String(d.id) === String(id));
        if (!item || item.isLoading) return;
        
        // Header, subtitle and status badge
        document.getElementById('m-title').textContent = item.name;
        
        const mProf = document.getElementById('m-professor');
        if (mProf) {
            if (item.professor && item.professor !== 'Desconhecido') {
                mProf.style.display = 'block';
                mProf.textContent = `Prof. ${item.professor}`;
            } else {
                mProf.style.display = 'none';
            }
        }
        
        const status = item.status ? item.status.status : 'Indefinido';
        const badge = document.getElementById('m-status-badge');
        badge.textContent = status;
        badge.className = 'badge ' + getStatusColor(status);
        
        const diffWidget = document.getElementById('m-diff-widget');
        if (diffWidget) {
            diffWidget.style.display = 'none';
            updateWidgetsRowVisibility();
        }

        if (item.professor && item.professor !== 'Desconhecido') {
            const cacheKey = `${reviewName(item)}|${item.professor}`;
            if (item.exigencia_media !== undefined) {
                renderDifficultyWidget(item.exigencia_media);
            } else if (window.courseRatings && window.courseRatings[cacheKey] !== undefined) {
                renderDifficultyWidget(window.courseRatings[cacheKey]);
            } else {
                fetch(`/api/avaliacoes/media?disciplina=${encodeURIComponent(reviewName(item))}&professor=${encodeURIComponent(item.professor)}`)
                    .then(r => r.json())
                    .then(d => {
                        if (window.courseRatings) window.courseRatings[cacheKey] = d.average;
                        item.exigencia_media = d.average; // Save to item for next time
                        renderDifficultyWidget(d.average);
                    })
                    .catch(e => console.error(e));
            }
        }
        
        // Status Widget (Atenção/Observação)
        const widget = document.getElementById('m-status-widget');
        const widgetVal = document.getElementById('m-status-val');
        const hasMsg = item.status && item.status.message;
        
        if (hasMsg) {
          widget.style.display = 'flex';
          widgetVal.textContent = item.status.message;
          
          const msgUpper = item.status.message.toUpperCase();
          const svgCircle = widget.querySelector('.ring-container svg circle:nth-child(2)');
          const svgBgCircle = widget.querySelector('.ring-container svg circle:nth-child(1)');
          const ringVal = widget.querySelector('.ring-val');
          
          let colorVar = 'var(--warning)';
          let bgColor = 'rgba(245,158,11,0.15)';
          let icon = '!';
          
          let swRgb = '245, 158, 11';
          let swColor = '#fbbf24';
          
          if (msgUpper.includes('APROVAD') || msgUpper.includes('CUMPRID') || msgUpper.includes('DISPENSAD')) {
            colorVar = 'var(--success)';
            bgColor = 'rgba(16,185,129,0.15)';
            icon = '✓';
            swRgb = '16, 185, 129';
            swColor = 'var(--success)';
          } else if (msgUpper.includes('REPROVAD') || msgUpper.includes('TRANCAD') || msgUpper.includes('CANCELAD')) {
            colorVar = 'var(--danger)';
            bgColor = 'rgba(239,68,68,0.15)';
            icon = '✕';
            swRgb = '239, 68, 68';
            swColor = 'var(--danger)';
          } else if (msgUpper.includes('MATRICULAD')) {
            colorVar = 'var(--accent)';
            bgColor = 'rgba(59,130,246,0.15)';
            icon = 'i';
            swRgb = '59, 130, 246';
            swColor = 'var(--accent)';
          }
          
          widget.style.setProperty('--sw-rgb', swRgb);
          widget.style.setProperty('--sw-color', swColor);
          
          if (svgCircle) svgCircle.setAttribute('stroke', colorVar);
          if (svgBgCircle) svgBgCircle.setAttribute('stroke', bgColor);
          if (ringVal) {
            ringVal.textContent = icon;
          }
          
        } else {
          widget.style.display = 'none';
        }
        
        updateWidgetsRowVisibility();
        
        // Grades Timeline
        const container = document.getElementById('m-grades-timeline');
        container.innerHTML = '';
        if (item.grades && item.grades.length > 0) {
          let html = '';
          item.grades.forEach(g => {
            if (g.type === 'group' && g.grades && g.grades.length > 0) {
              html += `
                <div class="unit-group">
                  <div class="unit-header">
                    <span class="uh-title">${g.name}</span>
                  </div>
                  <div class="av-list">
              `;
              g.grades.forEach(sg => {
                const val = sg.value;
                let valStr = '-';
                let colorClass = '';
                let progressWidth = 0;
                let bgColorClass = 'bg-warning';
                
                if (val !== null) {
                  valStr = val.toFixed(1);
                  colorClass = val >= 7.0 ? 'c-success' : (val >= 5.0 ? 'c-warning' : 'c-danger');
                  bgColorClass = val >= 7.0 ? 'bg-success' : (val >= 5.0 ? 'bg-warning' : 'bg-danger');
                  progressWidth = Math.min(100, Math.max(0, val * 10));
                }
                
                html += `
                  <div class="av-row">
                    <span class="av-label" title="${sg.name}">${sg.name}</span>
                    <div class="av-track"><div class="av-fill ${bgColorClass}" style="width: ${progressWidth}%;"></div></div>
                    <span class="av-value ${colorClass}">${valStr}</span>
                  </div>
                `;
              });
              html += `</div></div>`;
            } else {
              const val = g.value;
              let valStr = '-';
              let colorClass = '';
              let progressWidth = 0;
              let bgColorClass = 'bg-warning';
              
              if (val !== null) {
                valStr = val.toFixed(1);
                colorClass = val >= 7.0 ? 'c-success' : (val >= 5.0 ? 'c-warning' : 'c-danger');
                bgColorClass = val >= 7.0 ? 'bg-success' : (val >= 5.0 ? 'bg-warning' : 'bg-danger');
                progressWidth = Math.min(100, Math.max(0, val * 10));
              }
              html += `
                <div class="unit-group">
                  <div class="av-list" style="padding-left:0;">
                    <div class="av-row">
                      <span class="av-label" title="${g.name}">${g.name}</span>
                      <div class="av-track"><div class="av-fill ${bgColorClass}" style="width: ${progressWidth}%;"></div></div>
                      <span class="av-value ${colorClass}">${valStr}</span>
                    </div>
                  </div>
                </div>
              `;
            }
          });
          container.innerHTML = html;
        } else {
          container.innerHTML = '<div style="color:var(--text-muted); font-size:13px; text-align:center; width:100%; padding:20px 0;">Nenhuma nota lançada nesta disciplina.</div>';
        }

        // Inline Evaluation Logic
        const btnEvaluate = document.getElementById('m-btn-evaluate');
        const evalSection = document.getElementById('m-eval-section');
        const btnCancel = document.getElementById('m-btn-eval-cancel');
        const btnSubmit = document.getElementById('m-btn-eval-submit');

        // Initially hide until we know if user voted
        btnEvaluate.style.display = 'none';
        evalSection.classList.remove('active');
        btnEvaluate.classList.remove('active');
        const radios = evalSection.querySelectorAll('input[type="radio"]');
        radios.forEach(r => r.checked = false);

        // Remove old event listeners
        const newBtnEvaluate = btnEvaluate.cloneNode(true);
        btnEvaluate.parentNode.replaceChild(newBtnEvaluate, btnEvaluate);
        
        const newBtnCancel = btnCancel.cloneNode(true);
        btnCancel.parentNode.replaceChild(newBtnCancel, btnCancel);
        
        const newBtnSubmit = btnSubmit.cloneNode(true);
        btnSubmit.parentNode.replaceChild(newBtnSubmit, btnSubmit);

        function setupEvaluation(userVoted) {
            const temProfessor = item.professor && item.professor !== 'Desconhecido';
            const isCompleted = item.status && item.status.status && (
                item.status.status.includes('Aprovado') || 
                item.status.status.includes('Reprovado') || 
                item.status.status.includes('Concluído') || 
                item.status.status.includes('Cancelado') || 
                item.status.status.includes('Dispensado') || 
                item.status.status.includes('Trancado')
            );
            
            if (temProfessor && isCompleted) {
                newBtnEvaluate.style.display = 'flex';
                newBtnEvaluate.disabled = false;
                newBtnEvaluate.style.opacity = "1";
                newBtnEvaluate.style.cursor = "pointer";
                
                if (userVoted) {
                    newBtnEvaluate.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" style="stroke:currentColor; stroke-width:3; fill:none; stroke-linecap:round; stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"></polyline></svg> Avaliada';
                    newBtnEvaluate.style.background = "rgba(255, 255, 255, 0.05)";
                    newBtnEvaluate.style.border = "none";
                    newBtnEvaluate.style.color = "var(--text-muted)";
                    newBtnEvaluate.style.pointerEvents = "none";
                    newBtnEvaluate.disabled = true;
                } else {
                    newBtnEvaluate.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" style="stroke:currentColor; stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round;"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg> Avaliar';
                    newBtnEvaluate.style.background = "";
                    newBtnEvaluate.style.pointerEvents = "auto";
                    
                    newBtnEvaluate.addEventListener('click', () => {
                  evalSection.classList.toggle('active');
                  newBtnEvaluate.classList.toggle('active');
                });

                newBtnCancel.addEventListener('click', () => {
                  evalSection.classList.remove('active');
                  newBtnEvaluate.classList.remove('active');
                  radios.forEach(r => r.checked = false);
                });
                
                newBtnSubmit.addEventListener('click', async () => {
                  const checked = document.querySelector('input[name="m-rating"]:checked');
                  if(!checked) return alert("Por favor, selecione um nível de exigência de 1 a 5.");
                  
                  const val = parseInt(checked.value);
                  const payload = { itens: [{ disciplina: reviewName(item), professor: item.professor, nota: val, recusado: false }] };
                  
                  const oldText = newBtnSubmit.textContent;
                  newBtnSubmit.textContent = "Enviando...";
                  newBtnSubmit.disabled = true;
                  
                  try {
                    const response = await fetch('/api/avaliacoes/submeter', {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.APP_CONFIG.csrfToken
                      },
                      body: JSON.stringify(payload)
                    });
                    
                    if (response.ok) {
                      newBtnSubmit.textContent = "Sucesso!";
                      newBtnSubmit.style.background = "var(--success)";
                      item.user_voted = true;
                      setTimeout(() => {
                        evalSection.classList.remove('active');
                        newBtnEvaluate.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" style="stroke:currentColor; stroke-width:3; fill:none; stroke-linecap:round; stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"></polyline></svg> Avaliada';
                        newBtnEvaluate.style.background = "rgba(255, 255, 255, 0.05)";
                        newBtnEvaluate.style.border = "none";
                        newBtnEvaluate.style.color = "var(--text-muted)";
                        newBtnEvaluate.style.pointerEvents = "none";
                        newBtnEvaluate.disabled = true;
                        
                        newBtnSubmit.textContent = oldText;
                        newBtnSubmit.disabled = false;
                        newBtnSubmit.style.background = "";
                      }, 1000);
                    } else {
                      throw new Error("Erro na API");
                    }
                  } catch (e) {
                    console.error("Error submitting evaluation", e);
                    alert("Falha ao enviar avaliação.");
                    newBtnSubmit.textContent = oldText;
                    newBtnSubmit.disabled = false;
                  }
                });
                }
            }
        }

        // Fetch or use cached user_voted state
        const outerTemProfessor = item.professor && item.professor !== 'Desconhecido';
        const outerIsCompleted = item.status && item.status.status && (
            item.status.status.includes('Aprovado') || 
            item.status.status.includes('Reprovado') || 
            item.status.status.includes('Concluído') || 
            item.status.status.includes('Cancelado') || 
            item.status.status.includes('Dispensado') || 
            item.status.status.includes('Trancado')
        );

        if (outerTemProfessor) {
            const cacheKey = `${reviewName(item)}|${item.professor}`;
            
            if (item.user_voted !== undefined) {
                setupEvaluation(item.user_voted);
            } else if (window.courseUserVoted && window.courseUserVoted[cacheKey] !== undefined) {
                setupEvaluation(window.courseUserVoted[cacheKey]);
            } else {
                if (outerIsCompleted) {
                    newBtnEvaluate.style.display = 'flex';
                    newBtnEvaluate.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" style="stroke:currentColor; stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Carregando...';
                    newBtnEvaluate.disabled = true;
                    newBtnEvaluate.style.opacity = "0.7";
                    newBtnEvaluate.style.cursor = "wait";
                }
                fetch(`/api/avaliacoes/media?disciplina=${encodeURIComponent(reviewName(item))}&professor=${encodeURIComponent(item.professor)}`)
                    .then(r => r.json())
                    .then(d => {
                        if (!window.courseUserVoted) window.courseUserVoted = {};
                        window.courseUserVoted[cacheKey] = !!d.user_voted;
                        item.user_voted = !!d.user_voted;
                        setupEvaluation(item.user_voted);
                    })
                    .catch(e => {
                        console.error(e);
                        setupEvaluation(false); // fallback
                    });
            }
        } else {
            setupEvaluation(false);
        }
      }
    }

    let hasCheckedPendingReviews = false;
    async function checkPendingReviews() {
        if (hasCheckedPendingReviews) return;
        hasCheckedPendingReviews = true;
        
        try {
            const response = await fetch('/api/avaliacoes/pendentes');
            if (response.ok) {
                const pendData = await response.json();
                window.pendingReviewsList = pendData.pendentes || [];
                mRenderGroupedList();
                
                const currentSem = pendData.current_semester;
                const skipped = pendData.skipped_semesters || [];
                
                if (window.pendingReviewsList.length > 0) {
                    if (currentSem && skipped.includes(currentSem)) {
                        console.log("Reviews skipped for semester", currentSem);
                    } else {
                        window.currentSemesterForSkip = currentSem;
                        openReviewWizardModal(window.pendingReviewsList);
                    }
                    return;
                }
            }
        } catch (e) { console.error("Error checking pending reviews", e); }

        try {
            const pares = [];
            if (typeof data !== 'undefined' && Array.isArray(data)) {
                data.forEach(d => {
                    if (d.name && d.professor && d.professor !== 'Desconhecido') {
                        pares.push({disciplina: reviewName(d), professor: d.professor});
                    }
                });
            }
            if (pares.length > 0) {
                const response = await fetch('/api/avaliacoes/medias_lote', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
                    body: JSON.stringify({ pares })
                });
                if (response.ok) {
                    const loteData = await response.json();
                    window.courseRatings = loteData.averages || {};
                    window.courseUserVoted = loteData.user_voted || {};
                    mRenderGroupedList(); // re-render to show stars
                }
            } else {
                window.courseRatings = {};
                window.courseUserVoted = {};
            }
        } catch (e) { console.error("Error fetching medias em lote", e); }
    }

    function closeModal() { document.getElementById('modal').style.display = 'none'; }
    document.getElementById('modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });

    // Perfil injetado pelo servidor no HTML: pinta o histórico sem esperar o stream.
    if (window.__initialProfile) {
      profileData = window.__initialProfile;
      _buildMSemDropdown('Atual');
      checkPendingReviews();
    }
    // Iniciar a busca de dados
    startDataStream();

/* ========================================================================= */
/* FASE 2: WIZARD GAMIFICADO DE AVALIACOES NO DASHBOARD                      */
/* ========================================================================= */

let wizardPendingReviews = [];
let wizardCurrentCardIndex = 0;
let wizardEvaluatedItems = [];
let wizardComboCount = 0;

function formatWizardProfName(fullName) {
    if (!fullName || fullName.toUpperCase() === 'DESCONHECIDO') return fullName;
    const parts = fullName.trim().split(/\s+/);
    if (parts.length <= 1) return fullName;
    const preps = ['DE', 'DA', 'DO', 'DAS', 'DOS'];
    if (parts.length > 2 && preps.includes(parts[1].toUpperCase())) {
        return parts[0] + ' ' + parts[1] + ' ' + parts[2];
    }
    return parts[0] + ' ' + parts[1];
}

window.openReviewWizardModal = function(reviewsList) {
    wizardPendingReviews = reviewsList;
    wizardCurrentCardIndex = 0;
    wizardEvaluatedItems = [];
    wizardComboCount = 0;
    
    document.getElementById('review-wizard-overlay').style.display = 'flex';
    
    const container = document.getElementById('card-container');
    container.innerHTML = '';
    
    wizardPendingReviews.forEach((rev, idx) => {
        const card = document.createElement('div');
        card.className = `review-card ${idx === 0 ? 'active' : ''}`;
        card.id = `wizcard-${idx}`;
        card.innerHTML = `
            <div class="disc-name">${rev.disciplina}</div>
            <div class="prof-name">Prof. ${formatWizardProfName(rev.professor)}</div>
            
            <div class="rating-label">Quão exigente foi esta disciplina?</div>
            <div class="rating-group">
                <button class="btn-rate r1" onclick="wizardRateCard(${idx}, 1, event)">1</button>
                <button class="btn-rate r2" onclick="wizardRateCard(${idx}, 2, event)">2</button>
                <button class="btn-rate r3" onclick="wizardRateCard(${idx}, 3, event)">3</button>
                <button class="btn-rate r4" onclick="wizardRateCard(${idx}, 4, event)">4</button>
                <button class="btn-rate r5" onclick="wizardRateCard(${idx}, 5, event)">5</button>
            </div>
            
            <button class="btn-skip" onclick="wizardSkipCard(${idx})">Pular matéria</button>
        `;
        container.appendChild(card);
    });
    
    // Add skip all button at the end of the container
    const skipAllDiv = document.createElement('div');
    skipAllDiv.style.position = 'absolute';
    skipAllDiv.style.bottom = '-60px';
    skipAllDiv.style.left = '0';
    skipAllDiv.style.right = '0';
    skipAllDiv.style.textAlign = 'center';
    skipAllDiv.innerHTML = `<button style="background:none; border:none; color:var(--text-muted); font-size:12px; text-decoration:underline; cursor:pointer; opacity:0.8; transition:0.2s;" onmouseover="this.style.opacity='1'; this.style.color='#fff'" onmouseout="this.style.opacity='0.8'; this.style.color='var(--text-muted)'" onclick="wizardSkipSemester()">Pular todas as avaliações deste semestre</button>`;
    container.appendChild(skipAllDiv);
    
    wizardUpdateProgress();
};

function wizardUpdateProgress() {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    const total = wizardPendingReviews.length;
    const pct = ((wizardCurrentCardIndex) / total) * 100;
    fill.style.width = `${pct}%`;
    text.textContent = `${wizardCurrentCardIndex} de ${total} avaliadas`;
}

function wizardUpdateCombo(reset) {
    const badge = document.getElementById('combo-badge');
    if (reset) {
        wizardComboCount = 0;
        badge.classList.remove('active');
    } else {
        wizardComboCount++;
        if (wizardComboCount >= 2) {
            badge.textContent = `🔥 ${wizardComboCount}x Combo!`;
            badge.classList.add('active');
            badge.style.transform = 'scale(1.1)';
            setTimeout(() => badge.style.transform = 'scale(1)', 200);
        } else {
            badge.classList.remove('active');
        }
    }
}

window.wizardRateCard = function(idx, rating, event) {
    const rev = wizardPendingReviews[idx];
    wizardEvaluatedItems.push({
        disciplina: rev.disciplina,
        professor: rev.professor,
        nota: rating,
        recusado: false
    });

    wizardUpdateCombo(false);
    wizardNextCard(idx, 'exit-right');
};

window.wizardSkipCard = function(idx) {
    const rev = wizardPendingReviews[idx];
    wizardEvaluatedItems.push({
        disciplina: rev.disciplina,
        professor: rev.professor,
        nota: null,
        recusado: true
    });

    wizardUpdateCombo(true);
    wizardNextCard(idx, 'exit-left');
};

window.wizardSkipSemester = async function() {
    if (!window.currentSemesterForSkip) {
        document.getElementById('review-wizard-overlay').style.display = 'none';
        return;
    }
    try {
        await fetch('/api/avaliacoes/skip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
            body: JSON.stringify({ semester: window.currentSemesterForSkip })
        });
    } catch (e) {
        console.error("Error skipping semester", e);
    }
    document.getElementById('review-wizard-overlay').style.display = 'none';
};

function wizardNextCard(idx, exitClass) {
    const currentCard = document.getElementById(`wizcard-${idx}`);
    currentCard.classList.remove('active');
    currentCard.classList.add(exitClass);

    wizardCurrentCardIndex++;
    wizardUpdateProgress();

    if (wizardCurrentCardIndex < wizardPendingReviews.length) {
        const nxt = document.getElementById(`wizcard-${wizardCurrentCardIndex}`);
        nxt.classList.add('active');
    } else {
        wizardFinish();
    }
}

async function wizardFinish() {
    document.getElementById('card-container').innerHTML = `<div style="text-align:center; padding-top:100px; color:var(--success); font-weight:bold; font-size: 20px;">Salvando avaliações...</div>`;
    
    if (wizardEvaluatedItems.length > 0) {
        try {
            await fetch('/api/avaliacoes/submeter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CONFIG.csrfToken },
                body: JSON.stringify({ itens: wizardEvaluatedItems })
            });
        } catch(e) { console.error(e); }
    }
    
    document.getElementById('review-wizard-overlay').style.display = 'none';
}

// Build background grid for intro card
function buildGrid() {
  const table = document.getElementById('grid-table');
  if (!table) return;
  
  const DIAS = ['Seg','Ter','Qua','Qui','Sex','Sáb'];
  const BLOCOS = [
    {id:'M1', s:'07:00'}, {id:'M2', s:'07:55'}, {id:'M3', s:'08:55'}, {id:'M4', s:'09:50'}, {id:'M5', s:'10:50'}, {id:'M6', s:'11:45'},
    {id:'T1', s:'13:00'}, {id:'T2', s:'13:55'}, {id:'T3', s:'14:55'}, {id:'T4', s:'15:50'}, {id:'T5', s:'16:50'}, {id:'T6', s:'17:45'},
    {id:'N1', s:'18:45'}, {id:'N2', s:'19:40'}, {id:'N3', s:'20:30'}, {id:'N4', s:'21:20'}
  ];
  const GHOSTS = [ {b:2, d:3}, {b:6, d:5}, {b:11, d:2} ];
  
  let html = '<div class="gcell ghead"></div>';
  DIAS.forEach(d => html += `<div class="gcell ghead">${d}</div>`);

  BLOCOS.forEach((bloco, bi) => {
    html += `<div class="gcell glabel"><span class="code">${bloco.id}</span><span class="time">${bloco.s}</span></div>`;
    DIAS.forEach((d, di) => {
      const isGhost = GHOSTS.some(g => g.b === bi && g.d === di);
      const isFirstGhost = isGhost && GHOSTS[0].b === bi && GHOSTS[0].d === di;
      if (isGhost) {
        html += `<div class="gcell ghost"><span class="ghost-dot${isFirstGhost ? ' pulse' : ''}"></span></div>`;
      } else {
        html += `<div class="gcell"></div>`;
      }
    });
  });
  table.innerHTML = html;
}
setTimeout(buildGrid, 100);

// Redirecionamento automático via URL para tela de matrícula
window.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  if (params.has('matricula') || window.location.hash === '#matricula') {
    if (window.innerWidth >= 992) {
      if(typeof switchTab === 'function') switchTab('matricula');
    } else {
      if(typeof mSwitchTabFromNav === 'function') mSwitchTabFromNav('matricula');
    }
    
    // Iniciar o fluxo diretamente se desejar pular a introdução
    setTimeout(() => {
      if(typeof startMatriculaFlow === 'function') startMatriculaFlow();
    }, 150);
  }
});
