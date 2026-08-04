let data = [];
    let liveData = [];
    let isHistoryMode = false;
    let chart = null;
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
    let matriculaLevels = [];
    let selectedClassIds = [];
    let matriculaViewState = '';
    let isMatriculaLoaded = false;

    function startMatriculaFlow() {
      const btn = document.querySelector('#matricula-intro-card .m-btn-primary');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = 'Carregando turmas...';

      fetch('/api/matricula/status')
        .then(res => {
          if (!res.ok) {
            throw new Error('Falha ao autenticar ou carregar dados.');
          }
          return res.json();
        })
        .then(data => {
          if (data.error) {
            throw new Error(data.error);
          }
          matriculaLevels = data.levels || [];
          matriculaViewState = data.view_state || '';
          isMatriculaLoaded = true;
          
          renderMatriculaSelection();
          
          document.getElementById('matricula-intro-card').style.display = 'none';
          document.getElementById('matricula-selection-container').style.display = 'block';
        })
        .catch(err => {
          alert('Erro ao iniciar matrícula: ' + err.message);
        })
        .finally(() => {
          btn.disabled = false;
          btn.innerHTML = originalText;
        });
    }

    function renderMatriculaSelection() {
      const listContainer = document.getElementById('matricula-levels-list');
      if (!listContainer._equivBound) {
        listContainer._equivBound = true;
        listContainer.addEventListener('click', (event) => {
          const btn = event.target.closest('[data-equiv-code]');
          if (btn) showEquivalents(btn.dataset.equivCode, btn.dataset.equivPayload);
        });
      }
      listContainer.innerHTML = '';
      
      if (matriculaLevels.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted);">Nenhuma turma disponível no momento.</div>';
        return;
      }

      matriculaLevels.forEach(level => {
        const levelDiv = document.createElement('div');
        levelDiv.style.marginBottom = '24px';
        levelDiv.innerHTML = `<h4 style="color:var(--accent); font-weight:800; margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:6px;">${escapeHtml(level.level)}</h4>`;

        level.disciplines.forEach(disc => {
          const discDiv = document.createElement('div');
          discDiv.className = 'm-disc-group';

          // Equivalents trigger JS
          const equivBtnHtml = disc.equiv_onclick ? 
            `<button class="m-btn m-btn-secondary" style="padding:4px 8px; font-size:11px; border-radius:8px;" data-equiv-code="${escapeHtml(disc.code)}" data-equiv-payload="${escapeHtml(disc.equiv_onclick)}">🔗 Equivalentes</button>` : '';

          discDiv.innerHTML = `
            <div class="m-disc-title">
              <span>${escapeHtml(disc.code)} - ${escapeHtml(disc.name)}</span>
              ${equivBtnHtml}
            </div>
            <div class="m-classes-list"></div>
          `;

          const classesList = discDiv.querySelector('.m-classes-list');
          disc.classes.forEach(cls => {
            const classItem = document.createElement('div');
            classItem.className = 'm-class-item' + (selectedClassIds.includes(cls.class_id) ? ' selected' : '');
            classItem.onclick = (e) => {
              // Avoid triggering if clicked inside buttons/checkboxes directly
              toggleSelectClass(cls.class_id);
            };

            classItem.innerHTML = `
              <div class="m-class-chk"></div>
              <div class="m-class-details">
                <div class="m-class-code">${escapeHtml(cls.class_code)}</div>
                <div class="m-class-info"><strong>Prof:</strong> ${escapeHtml(cls.teacher || 'A definir')}</div>
                <div class="m-class-info"><strong>Horário:</strong> ${escapeHtml(cls.schedule)} | <strong>Local:</strong> ${escapeHtml(cls.location || 'A definir')}</div>
              </div>
            `;
            classesList.appendChild(classItem);
          });

          levelDiv.appendChild(discDiv);
        });

        listContainer.appendChild(levelDiv);
      });
      
      updateSummaryBar();
    }

    function toggleSelectClass(classId) {
      const idx = selectedClassIds.indexOf(classId);
      if (idx === -1) {
        selectedClassIds.push(classId);
      } else {
        selectedClassIds.splice(idx, 1);
      }
      
      // Update DOM classes
      renderMatriculaSelection();
      checkLocalConflicts();
    }

    function resetMatriculaSelection() {
      selectedClassIds = [];
      renderMatriculaSelection();
      checkLocalConflicts();
    }

    function findClassById(classId) {
      for (const lvl of matriculaLevels) {
        for (const disc of lvl.disciplines) {
          for (const cls of disc.classes) {
            if (cls.class_id === classId) {
              return { cls: cls, disc: disc };
            }
          }
        }
      }
      return null;
    }

    // JS-based schedule conflict detector matching the python logic
    function parseSchedule(scheduleStr) {
      const regex = /^([2-7]+)([MNT])([1-6]+)$/;
      const match = scheduleStr.match(regex);
      if (!match) return [];
      const days = match[1].split('').map(Number);
      const shift = match[2];
      const hours = match[3].split('').map(Number);
      const slots = [];
      days.forEach(d => {
        hours.forEach(h => {
          slots.push(`${d}-${shift}-${h}`);
        });
      });
      return slots;
    }

    function checkLocalConflicts() {
      const slotMap = {};
      const conflicts = [];
      
      selectedClassIds.forEach(id => {
        const item = findClassById(id);
        if (!item) return;
        const cls = item.cls;
        const slots = parseSchedule(cls.schedule);
        
        slots.forEach(slot => {
          if (slotMap[slot]) {
            conflicts.push({
              slot: slot,
              class1: slotMap[slot],
              class2: item
            });
          }
          slotMap[slot] = item;
        });
      });

      const alertBox = document.getElementById('matricula-conflict-alert');
      const conflictList = document.getElementById('matricula-conflict-list');
      const nextBtn = document.getElementById('btn-submit-selection');

      if (conflicts.length > 0) {
        alertBox.style.display = 'block';
        nextBtn.disabled = true;
        
        // Render conflict descriptions
        const uniqueConflicts = [];
        const seenStr = new Set();
        conflicts.forEach(conf => {
          const key = [conf.class1.cls.class_id, conf.class2.cls.class_id].sort().join('-');
          if (!seenStr.has(key)) {
            seenStr.add(key);
            uniqueConflicts.push(conf);
          }
        });

        conflictList.innerHTML = uniqueConflicts.map(conf => {
          return `• <strong>${conf.class1.disc.code} (${conf.class1.cls.class_code})</strong> e <strong>${conf.class2.disc.code} (${conf.class2.cls.class_code})</strong> possuem choque de horário (${conf.class1.cls.schedule} vs ${conf.class2.cls.schedule}).`;
        }).join('<br>');
      } else {
        alertBox.style.display = 'none';
        nextBtn.disabled = false;
        conflictList.innerHTML = '';
      }
    }

    function updateSummaryBar() {
      const countEl = document.getElementById('matricula-selected-count');
      const listEl = document.getElementById('matricula-selected-list');
      
      countEl.innerText = `${selectedClassIds.length} turma(s) selecionada(s)`;
      listEl.innerHTML = '';

      selectedClassIds.forEach(id => {
        const item = findClassById(id);
        if (item) {
          const div = document.createElement('div');
          div.innerHTML = `• ${escapeHtml(item.disc.code)} - ${escapeHtml(item.cls.class_code)} (${escapeHtml(item.cls.schedule)})`;
          listEl.appendChild(div);
        }
      });
    }

    function showEquivalents(discCode, equivOnclick) {
      // Clean overlay modal showing equivalent disciplines
      const isDev = true; 
      
      let contentHtml = '';
      if (discCode === 'PEDL092') {
        contentHtml = `
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:16px; padding:16px;">
            <p><strong>Disciplinas Equivalentes Encontradas:</strong></p>
            <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:8px; margin-bottom:8px;">
              <strong>PED090 - ANTROPOLOGIA DA EDUCAÇÃO</strong> (Carga: 60h)
              <br><span style="color:#4caf50;">Turma 01 (Prof: MARCOS VINICIUS) - 4M1234</span>
            </div>
            <p style="font-size:12px; color:var(--text-muted);">Essa equivalência é aceita para cumprir os requisitos da estrutura curricular de Geografia.</p>
          </div>
        `;
      } else {
        contentHtml = `
          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:16px; padding:16px;">
            <p><strong>Consulta de Equivalentes (Gatilho SIGAA):</strong></p>
            <code>${equivOnclick}</code>
            <p style="font-size:12px; color:var(--text-muted); margin-top:8px;">Em ambiente de desenvolvimento, emulamos a verificação da expressão equivalente cadastrada no plano de curso.</p>
          </div>
        `;
      }

      const overlay = document.createElement('div');
      overlay.className = 'modal-active';
      overlay.style.position = 'fixed';
      overlay.style.top = '0';
      overlay.style.left = '0';
      overlay.style.width = '100vw';
      overlay.style.height = '100vh';
      overlay.style.background = 'rgba(0,0,0,0.85)';
      overlay.style.zIndex = '9999';
      overlay.style.display = 'flex';
      overlay.style.alignItems = 'center';
      overlay.style.justifyContent = 'center';
      overlay.style.backdropFilter = 'blur(10px)';

      overlay.innerHTML = `
        <div class="m-matricula-card" style="width:90%; max-width:450px; position:relative; animation: modalEnter 0.3s ease;">
          <button class="btn-close" style="top:15px; right:15px;" onclick="this.closest('.modal-active').remove()">X</button>
          <h3 style="margin-top:0;">Equivalências: ${discCode}</h3>
          ${contentHtml}
        </div>
      `;
      document.body.appendChild(overlay);
    }

    function submitMatriculaSelection() {
      if (selectedClassIds.length === 0) {
        alert('Selecione pelo menos uma turma.');
        return;
      }
      
      const btn = document.getElementById('btn-submit-selection');
      btn.disabled = true;
      btn.innerText = 'Processando...';

      fetch('/api/matricula/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.APP_CONFIG.csrfToken
        },
        body: JSON.stringify({
          selected_class_ids: selectedClassIds,
          view_state: matriculaViewState
        })
      })
      .then(res => {
        if (!res.ok) throw new Error('Erro de comunicação com o servidor.');
        return res.json();
      })
      .then(data => {
        if (data.error) throw new Error(data.error);
        
        // Show Step 3
        document.getElementById('matricula-selection-container').style.display = 'none';
        document.getElementById('matricula-review-container').style.display = 'block';
        
        // Render schedule grid table
        renderTimetableGrid();
      })
      .catch(err => {
        alert(err.message);
      })
      .finally(() => {
        btn.disabled = false;
        btn.innerText = 'Prosseguir ➔';
      });
    }

    function renderTimetableGrid() {
      const container = document.getElementById('matricula-grid-table-container');
      container.innerHTML = '';

      const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
      const dayCodes = [2, 3, 4, 5, 6, 7];
      const shifts = ['M', 'T', 'N'];
      const shiftHours = {
        'M': [1, 2, 3, 4, 5, 6],
        'T': [1, 2, 3, 4, 5, 6],
        'N': [1, 2, 3, 4]
      };

      let tableHtml = `
        <table class="m-timetable-table">
          <thead>
            <tr>
              <th>Horário</th>
              ${days.map(d => `<th>${d}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
      `;

      // Build rows
      shifts.forEach(shift => {
        shiftHours[shift].forEach(hour => {
          const rowCode = `${shift}${hour}`;
          tableHtml += `<tr><td><strong>${rowCode}</strong></td>`;
          
          dayCodes.forEach(day => {
            const slotKey = `${day}-${shift}-${hour}`;
            
            // Check if any selected class occupies this slot
            let occupiedClass = null;
            let occupiedDisc = null;
            selectedClassIds.forEach(id => {
              const item = findClassById(id);
              if (item) {
                const slots = parseSchedule(item.cls.schedule);
                if (slots.includes(slotKey)) {
                  occupiedClass = item.cls;
                  occupiedDisc = item.disc;
                }
              }
            });

            if (occupiedClass) {
              tableHtml += `<td class="m-timetable-slot-active" title="${escapeHtml(occupiedDisc.name)}">${escapeHtml(occupiedDisc.code)}</td>`;
            } else {
              tableHtml += `<td>---</td>`;
            }
          });
          
          tableHtml += '</tr>';
        });
      });

      tableHtml += '</tbody></table>';
      container.innerHTML = tableHtml;
    }

    function backToSelection() {
      document.getElementById('matricula-review-container').style.display = 'none';
      document.getElementById('matricula-selection-container').style.display = 'block';
    }

    function finalizeMatricula() {
      const password = document.getElementById('matricula-confirm-password').value;
      const errorEl = document.getElementById('matricula-confirm-error');
      const btn = document.getElementById('btn-finalize-matricula');
      
      errorEl.style.display = 'none';
      btn.disabled = true;
      btn.innerText = 'Enviando ao SIGAA...';

      fetch('/api/matricula/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.APP_CONFIG.csrfToken
        },
        body: JSON.stringify({
          password: password
        })
      })
      .then(res => {
        return res.json().then(data => {
          if (!res.ok) {
            throw new Error(data.message || 'Senha incorreta ou erro de validação.');
          }
          return data;
        });
      })
      .then(data => {
        // Step 4: Success
        document.getElementById('matricula-review-container').style.display = 'none';
        document.getElementById('matricula-success-container').style.display = 'block';
        document.getElementById('matricula-success-msg').innerText = data.message;
      })
      .catch(err => {
        errorEl.innerText = err.message;
        errorEl.style.display = 'block';
      })
      .finally(() => {
        btn.disabled = false;
        btn.innerText = 'Confirmar e Gravar ➔';
      });
    }

    function restartMatriculaWizard() {
      selectedClassIds = [];
      document.getElementById('matricula-success-container').style.display = 'none';
      document.getElementById('matricula-intro-card').style.display = 'block';
      document.getElementById('matricula-confirm-password').value = '';
    }

    function loadMatricula() {
      // Lazy load indicator
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
      const itemsWithFreq = items.filter(d => d.frequency && !d.frequency.nao_lancada);
      
      let overallAvg = 0, sumTotalFaltas = 0, sumMaxFaltas = 0;
      let critCount = 0;
      let totalDiscs = itemsWithFreq.length;
      
      if (totalDiscs > 0) {
        overallAvg = itemsWithFreq.reduce((s, d) => s + d.frequency.percent, 0) / totalDiscs;
        sumTotalFaltas = itemsWithFreq.reduce((s, d) => s + d.frequency.total_faltas, 0);
        sumMaxFaltas = itemsWithFreq.reduce((s, d) => s + d.frequency.max_faltas, 0);
        critCount = itemsWithFreq.filter(d => (d.frequency.max_faltas - d.frequency.total_faltas) <= 1).length;
      }

      const statGrid = document.createElement('div');
      statGrid.className = 'stat-grid';
      statGrid.innerHTML = `
        <div class="stat-box"><div class="stat-val" style="color:#fff">${totalDiscs}</div><div class="stat-lbl">Matérias</div></div>
        <div class="stat-box"><div class="stat-val" style="color:var(--danger)">${critCount}</div><div class="stat-lbl">Críticas</div></div>
        <div class="stat-box"><div class="stat-val" style="color:var(--safe)">${Math.max(0, sumMaxFaltas - sumTotalFaltas)}</div><div class="stat-lbl">Restantes Totais</div></div>
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
        if (!a.frequency || a.frequency.nao_lancada) return 1;
        if (!b.frequency || b.frequency.nao_lancada) return -1;
        const remA = a.frequency.max_faltas - a.frequency.total_faltas;
        const remB = b.frequency.max_faltas - b.frequency.total_faltas;
        return remA - remB;
      });

      sortedItems.forEach(item => {
        const div = document.createElement('div');
        
        if (!item.frequency || item.frequency.nao_lancada) {
          div.className = 'freq-item';
          div.innerHTML = `
            <div class="freq-item-head">
              <div class="freq-item-info">
                <div class="freq-item-subject" style="color:var(--text-muted);">${escapeHtml(item.name)}</div>
                <div class="freq-item-meta">Frequência não lançada</div>
              </div>
            </div>
          `;
          listContainer.appendChild(div);
          return;
        }

        const { total_faltas, max_faltas } = item.frequency;
        const remaining = Math.max(0, max_faltas - total_faltas);
        const aulas_total = item.frequency.aulas_total || (max_faltas * 4);
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
              <div class="freq-item-meta">${total_faltas} de ${aulas_total} aulas</div>
            </div>
            <div class="freq-item-badge ${badgeClass}">${remaining} restante${remaining !== 1 ? 's' : ''}</div>
            <div class="freq-chevron">▾</div>
          </div>
          <div class="freq-item-body">
            <div class="freq-item-body-inner">
              <div class="freq-body-row"><span>Limite da disciplina</span><span>${max_faltas} faltas</span></div>
              <div class="freq-body-row"><span>Faltas registradas</span><span>${total_faltas}</span></div>
              <div class="freq-dates-row" style="margin-top:8px;">${chipsHtml}</div>
            </div>
          </div>
        `;
        listContainer.appendChild(div);
      });
    }


    function renderPriority() {
      const list = document.getElementById('priority-list');
      const header = document.getElementById('priority-header');
      list.innerHTML = '';
      const priorityItems = data
        .filter(d => !d.isLoading && d.status)
        .filter(d => d.status.is_critical || d.status.needed > 0)
        .sort((a, b) => b.status.needed - a.status.needed);
      if (priorityItems.length === 0) {
        header.style.display = 'none'; list.style.display = 'none';
      } else {
        header.style.display = 'block'; list.style.display = 'block';
        priorityItems.forEach(c => {
          const div = document.createElement('div');
          div.className = 'card'; div.style.padding = '12px';
          div.innerHTML = `<div style="font-weight:700">${escapeHtml(c.name)}</div>
          <div style="font-size:12px; color:var(--text-muted)">
            ${c.status.is_critical ? '<span style="color:var(--danger)">STATUS CRÍTICO</span>' : `Falta ${c.status.needed.toFixed(1)} pts`}
          </div>`;
          list.appendChild(div);
        });
      }
    }

    function renderChart() {
      if (typeof Chart === 'undefined') return; // chart.js (defer) ainda não carregou
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
      renderPriority();
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
                  pares.push({disciplina: d.name, professor: d.professor});
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


    const ACHIEVEMENTS_DB = [
      { id: 'nerd_supremo', icon: '📘', name: 'Nerd Supremo', desc: 'Tirar 10 em qualquer disciplina', check: (d) => d.some(c => hasGradeVal(c, 10)) },
      { id: 'genio_incompreendido', icon: '📘', name: 'Gênio Incompreendido', desc: 'Média 9+ em 3 matérias', check: (d) => d.filter(c => c.status && c.status.average >= 9).length >= 3 },
      { id: 'sobrevivente', icon: '🔥', name: 'Sobrevivente', desc: 'Passar na recuperação/final', check: (d) => d.some(c => c.status && (c.status.status === 'Recuperação' || c.status.status === 'Prova Final')) },
      { id: 'onipresente', icon: '🕒', name: 'Onipresente', desc: '100% de Frequência', check: (d) => d.some(c => c.frequency && c.frequency.percent === 0) },
      { id: 'cartola', icon: '📝', name: 'Cartola do Semestre', desc: 'Todas notas > 8', check: (d) => d.length > 0 && d.every(c => c.status && c.status.average > 8) }
    ];

    function hasGradeVal(course, val) {
      if (!course.grades) return false;
      const check = (list) => { for (let g of list) { if (g.value === val) return true; if (g.grades) if (check(g.grades)) return true; } return false; };
      return check(course.grades);
    }

    function getUnlockedAchievements() {
      const validData = data.filter(d => !d.isLoading);
      return ACHIEVEMENTS_DB.map(ach => ({ ...ach, unlocked: ach.check(validData) }));
    }

    function renderAchievements() {
      const list = document.getElementById('achievements-list');
      list.innerHTML = '';
      const achs = getUnlockedAchievements().sort((a, b) => (b.unlocked ? 1 : 0) - (a.unlocked ? 1 : 0));
      achs.forEach(a => {
        const div = document.createElement('div');
        div.className = 'm-item';
        if (!a.unlocked) div.style.opacity = '0.4';
        div.innerHTML = `
        <div class="m-item-bar" style="background:${a.unlocked ? 'var(--success)' : '#444'}"></div>
        <div style="font-size:32px; margin-right:16px;">${a.icon}</div>
        <div class="m-item-body">
          <div class="m-item-name" style="color:${a.unlocked ? '#fff' : 'var(--text-muted)'}">${a.name}</div>
          <div class="m-item-sub">${a.desc}</div>
        </div>
        <div class="m-item-right">
          <div style="font-size:10px; font-weight:800; color:${a.unlocked ? 'var(--success)' : 'var(--text-muted)'}">
            ${a.unlocked ? 'DESBLOQUEADO' : 'BLOQUEADO'}
          </div>
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
            const cacheKey = `${item.name}|${item.professor}`;
            if (item.exigencia_media !== undefined) {
                renderDifficultyWidget(item.exigencia_media);
            } else if (window.courseRatings && window.courseRatings[cacheKey] !== undefined) {
                renderDifficultyWidget(window.courseRatings[cacheKey]);
            } else {
                fetch(`/api/avaliacoes/media?disciplina=${encodeURIComponent(item.name)}&professor=${encodeURIComponent(item.professor)}`)
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
                  const payload = { itens: [{ disciplina: item.name, professor: item.professor, nota: val, recusado: false }] };
                  
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
            const cacheKey = `${item.name}|${item.professor}`;
            
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
                fetch(`/api/avaliacoes/media?disciplina=${encodeURIComponent(item.name)}&professor=${encodeURIComponent(item.professor)}`)
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
                        pares.push({disciplina: d.name, professor: d.professor});
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

