/* Static mock UI — hash routing, no backend */
(function () {
  const state = {
    lang: localStorage.getItem('mock-ui-lang') || 'en',
    loggedIn: false,
    projectId: 'p1',
    projectTab: 'mapping',
    selectedFinding: 'f1',
    isoClause: '7.5',
    isoLang: 'en',
  };

  function t(key) {
    return (MOCK.i18n[state.lang] || MOCK.i18n.en)[key] || key;
  }

  function applyLang() {
    document.documentElement.lang = state.lang;
    document.documentElement.dir = state.lang === 'he' ? 'rtl' : 'ltr';
    localStorage.setItem('mock-ui-lang', state.lang);
  }

  function route() {
    const hash = location.hash.slice(1) || '/login';
    return hash.startsWith('/') ? hash : '/' + hash;
  }

  function nav(path) {
    location.hash = path;
    render();
  }

  function banner() {
    return `<div class="mock-banner">${t('mockBanner')}</div>`;
  }

  function langSwitcher() {
    return `
      <div class="btn-group" style="margin:0">
        <button class="btn btn-sm ${state.lang === 'en' ? 'btn-primary' : ''}" onclick="MockUI.setLang('en')">EN</button>
        <button class="btn btn-sm ${state.lang === 'he' ? 'btn-primary' : ''}" onclick="MockUI.setLang('he')">HE</button>
      </div>`;
  }

  function sidebar(active) {
    const admin = MOCK.user.roles.includes('admin');
    return `
      <aside class="sidebar">
        <div class="brand">${t('appTitle')}</div>
        <nav>
          <a href="#/projects" class="${active === 'projects' ? 'active' : ''}">${t('projects')}</a>
          <a href="#/iso" class="${active === 'iso' ? 'active' : ''}">${t('isoViewer')}</a>
          ${admin ? `
            <div class="section-label">${t('knowledge')}</div>
            <a href="#/admin/iso" class="${active === 'admin-iso' ? 'active' : ''}">ISO standards</a>
            <a href="#/admin/samples" class="${active === 'admin-samples' ? 'active' : ''}">Sample reports</a>
            <a href="#/admin/templates" class="${active === 'admin-templates' ? 'active' : ''}">Templates</a>
            <a href="#/admin/instructions" class="${active === 'admin-instr' ? 'active' : ''}">${t('instructions')}</a>
            <a href="#/admin/users" class="${active === 'admin-users' ? 'active' : ''}">${t('users')}</a>
            <a href="#/admin/settings" class="${active === 'admin-settings' ? 'active' : ''}">${t('settings')}</a>
          ` : ''}
        </nav>
      </aside>`;
  }

  function shell(active, body) {
    return `
      ${banner()}
      <div class="layout">
        ${sidebar(active)}
        <div class="main">
          <header class="topbar">
            ${langSwitcher()}
            <span class="user">${MOCK.user.email} · ${MOCK.user.roles.join(', ')}</span>
            <button class="btn btn-sm" onclick="MockUI.logout()">${t('logout')}</button>
          </header>
          <div class="content">${body}</div>
        </div>
      </div>`;
  }

  function pageLogin() {
    return `
      ${banner()}
      <div class="login-page">
        <div class="login-card">
          ${langSwitcher()}
          <h1 style="margin-top:1rem">${t('appTitle')}</h1>
          <p class="sub">Mock preview — Google OAuth &amp; admin bootstrap</p>
          <button class="btn google-btn" onclick="MockUI.login()">
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6.01c4.51-4.18 7.09-10.36 7.09-17.66z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6.01c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
            ${t('googleSignIn')}
          </button>
          <button class="btn btn-primary" onclick="MockUI.login()">${t('devLogin')}</button>
          <p style="margin-top:1rem;font-size:0.8rem;color:var(--muted)">
            Admins: ${MOCK.admins.join(', ')}
          </p>
        </div>
      </div>`;
  }

  function pageProjects() {
    const rows = MOCK.projects.map((p) => `
      <tr onclick="MockUI.openProject('${p.id}')" style="cursor:pointer">
        <td><strong>${p.name}</strong><div class="progress-bar"><span style="width:${p.progress}%"></span></div></td>
        <td>${p.standards.join(', ')}</td>
        <td><span class="badge badge-${p.status}">${p.status}</span></td>
        <td>${p.progress}%</td>
      </tr>`).join('');
    return shell('projects', `
      <h1>${t('projects')}</h1>
      <div class="btn-group">
        <button class="btn btn-primary">${t('newProject')}</button>
      </div>
      <div class="card" style="padding:0;overflow:hidden">
        <table>
          <thead><tr><th>Name</th><th>Standards</th><th>Status</th><th>Progress</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`);
  }

  function pageProject() {
    const p = MOCK.projects.find((x) => x.id === state.projectId) || MOCK.projects[0];
    const tabs = ['context', 'findings', 'mapping', 'coverage', 'exports'];
    const tabLabels = { context: t('context'), findings: t('findings'), mapping: t('mapping'), coverage: t('coverage'), exports: t('exports') };
    const tabBtns = tabs.map((tab) =>
      `<button class="${state.projectTab === tab ? 'active' : ''}" onclick="MockUI.setTab('${tab}')">${tabLabels[tab]}</button>`
    ).join('');

    let body = '';
    if (state.projectTab === 'context') {
      body = `
        <div class="form-group"><label>Industry</label><input value="Medical devices manufacturing" /></div>
        <div class="form-group"><label>Sites</label><input value="2" /></div>
        <div class="form-group"><label>Main processes</label><textarea>Design, production, sterilization, distribution</textarea></div>
        <button class="btn btn-primary">Save</button>`;
    } else if (state.projectTab === 'findings') {
      body = `<ul class="finding-list">${MOCK.findings.map((f) =>
        `<li>${f.text} <span class="badge badge-${f.status === 'pending' ? 'draft' : 'approved'}">${f.status}</span></li>`
      ).join('')}</ul>
        <div class="form-group" style="margin-top:1rem"><label>Add finding</label><textarea placeholder="Paste or type finding…"></textarea></div>
        <button class="btn btn-primary">Add</button>`;
    } else if (state.projectTab === 'mapping') {
      const sel = MOCK.findings.find((f) => f.id === state.selectedFinding);
      const clause = MOCK.isoClauses['7.5'];
      body = `
        <div class="btn-group">
          <button class="btn">${t('runAuto')}</button>
          <button class="btn btn-primary">${t('approve')}</button>
        </div>
        <div class="grid3">
          <div class="card">
            <h3>${t('findings')}</h3>
            <ul class="finding-list">${MOCK.findings.map((f) =>
              `<li class="${f.id === state.selectedFinding ? 'selected' : ''}" onclick="MockUI.selectFinding('${f.id}')">${f.text.slice(0, 55)}…</li>`
            ).join('')}</ul>
          </div>
          <div class="card">
            <h3>Mapping pairs</h3>
            ${MOCK.mappings.map((m) => `
              <div class="mapping-row">
                <span><strong>${m.clause}</strong> ${m.title}</span>
                <span><span class="badge badge-${m.severity}">${m.severity}</span> ${m.relevance}%</span>
              </div>`).join('')}
            <div class="form-group" style="margin-top:0.75rem"><label>Add clause</label><input value="7.5" /></div>
          </div>
          <div class="card">
            <h3>Clause preview</h3>
            <div class="bilingual-grid">
              <div class="pane iso-ltr"><div class="pane-label">English</div><strong>${clause.en.title}</strong><p>${clause.en.text}</p></div>
              <div class="pane iso-rtl"><div class="pane-label">עברית</div><strong>${clause.he.title}</strong><p>${clause.he.text}</p></div>
            </div>
          </div>
        </div>
        <p style="color:var(--muted);font-size:0.8rem;margin-top:0.5rem">Selected: ${sel ? sel.text.slice(0, 80) : ''}…</p>`;
    } else if (state.projectTab === 'coverage') {
      body = `
        <table><thead><tr><th>Clause</th><th>Status</th></tr></thead>
        <tbody>
          <tr><td>4.1</td><td><span class="badge badge-approved">compliant</span></td></tr>
          <tr><td>5.1</td><td><span class="badge badge-draft">not checked</span></td></tr>
          <tr><td>7.5</td><td><span class="badge badge-major">NC</span></td></tr>
          <tr><td>8.3</td><td><span class="badge badge-minor">N/A</span></td></tr>
        </tbody></table>`;
    } else {
      body = `
        <p style="color:var(--warn);margin-bottom:1rem">✓ Mapping approved — exports enabled</p>
        <div class="btn-group">
          <button class="btn btn-primary">Excel mapping (Hebrew)</button>
          <button class="btn btn-primary">DOCX regulatory report (RTL)</button>
        </div>`;
    }

    const steps = ['context', 'findings', 'mapping', 'exports'];
    const stepHtml = steps.map((s, i) => {
      const done = i < 2 || (s === 'mapping' && p.status !== 'findings');
      const cur = state.projectTab === s;
      return `<span class="step ${done ? 'done' : ''} ${cur ? 'current' : ''}">${tabLabels[s] || s}</span>`;
    }).join('');

    return shell('projects', `
      <a href="#/projects" style="font-size:0.875rem">← ${t('projects')}</a>
      <h1>${p.name}</h1>
      <p style="color:var(--muted);margin-bottom:1rem">${p.standards.join(' + ')} · edition 2015</p>
      <div class="stepper">${stepHtml}</div>
      <div class="tabs">${tabBtns}</div>
      <div class="card">${body}</div>`);
  }

  function pageIso() {
    const ids = Object.keys(MOCK.isoClauses);
    const c = MOCK.isoClauses[state.isoClause];
    const list = ids.map((id) =>
      `<li><button class="btn btn-sm ${id === state.isoClause ? 'btn-primary' : ''}" onclick="MockUI.setIsoClause('${id}')">${id} — ${MOCK.isoClauses[id].en.title}</button></li>`
    ).join('');
    const single = state.isoLang === 'he' ? c.he : c.en;
    return shell('iso', `
      <h1>${t('isoTitle')}</h1>
      <div class="btn-group">
        <select onchange="MockUI.setIsoLang(this.value)" style="max-width:8rem">
          <option value="en" ${state.isoLang === 'en' ? 'selected' : ''}>English</option>
          <option value="he" ${state.isoLang === 'he' ? 'selected' : ''}>עברית</option>
        </select>
      </div>
      <div class="grid2">
        <div class="card"><h3>Clauses</h3><ul style="list-style:none;display:flex;flex-direction:column;gap:0.35rem">${list}</ul></div>
        <div class="card">
          <h3>${state.isoClause} — ${single.title}</h3>
          <div class="${state.isoLang === 'he' ? 'iso-rtl' : 'iso-ltr'}"><p>${single.text}</p></div>
        </div>
      </div>
      <h2 style="margin-top:1.5rem">${t('bilingual')}</h2>
      <div class="bilingual-grid">
        <div class="pane iso-ltr"><div class="pane-label">English (LTR)</div><strong>${c.en.title}</strong><p>${c.en.text}</p></div>
        <div class="pane iso-rtl"><div class="pane-label">עברית (RTL)</div><strong>${c.he.title}</strong><p>${c.he.text}</p></div>
      </div>`);
  }

  function pageAdminUsers() {
    const rows = MOCK.users.map((u) =>
      `<tr><td>${u.email}</td><td>${u.name}</td><td>${u.roles.join(', ')}</td></tr>`
    ).join('');
    return shell('admin-users', `
      <h1>${t('users')}</h1>
      <div class="card">
        <div class="grid2">
          <div class="form-group"><label>Email</label><input placeholder="user@company.com" /></div>
          <div class="form-group"><label>Role</label><select><option>consultant</option><option>supervisor</option><option>admin</option></select></div>
        </div>
        <button class="btn btn-primary">${t('inviteUser')}</button>
      </div>
      <div class="card" style="padding:0;overflow:hidden">
        <table><thead><tr><th>Email</th><th>Name</th><th>Roles</th></tr></thead><tbody>${rows}</tbody></table>
      </div>`);
  }

  function pageAdminCorpus(type, title, active) {
    const items = MOCK.corpus[type] || [];
    const rows = items.map((i) => `<tr><td>${i.name}</td><td>${i.chunks}</td><td>${i.status}</td></tr>`).join('');
    return shell(active, `
      <h1>${title}</h1>
      <div class="btn-group"><button class="btn btn-primary">Upload</button><button class="btn">Re-index</button></div>
      <div class="card" style="padding:0;overflow:hidden">
        <table><thead><tr><th>Name</th><th>Chunks</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="3">No documents yet</td></tr>'}</tbody></table>
      </div>`);
  }

  function pageAdminInstructions() {
    return shell('admin-instr', `
      <h1>${t('instructions')}</h1>
      <div class="tabs">
        <button class="active">iso_map_and_score</button>
        <button>report_narrative</button>
        <button>corrective_action_draft</button>
      </div>
      <div class="card">
        <div class="form-group"><label>Prompt body</label>
          <textarea rows="10">Map the following finding to at most 3 ISO {{standard}} clauses with relevance ≥50%: {{finding}}</textarea>
        </div>
        <button class="btn btn-primary">Publish version</button>
      </div>`);
  }

  function pageAdminSettings() {
    return shell('admin-settings', `
      <h1>${t('settings')}</h1>
      <div class="card">
        <table>
          <tr><td>Bootstrap admins</td><td>${MOCK.admins.join(', ')}</td></tr>
          <tr><td>LLM aliases</td><td>iso-mapper, iso-report, iso-embed</td></tr>
          <tr><td>Google OAuth</td><td>GOOGLE_CLIENT_ID (production)</td></tr>
        </table>
      </div>`);
  }

  function render() {
    applyLang();
    const r = route();
    const app = document.getElementById('app');

    if (!state.loggedIn && r !== '/login') {
      nav('/login');
      return;
    }

    if (r === '/login') {
      app.innerHTML = pageLogin();
      return;
    }

    if (r === '/projects') app.innerHTML = pageProjects();
    else if (r.startsWith('/project/')) app.innerHTML = pageProject();
    else if (r === '/iso') app.innerHTML = pageIso();
    else if (r === '/admin/users') app.innerHTML = pageAdminUsers();
    else if (r === '/admin/iso') app.innerHTML = pageAdminCorpus('iso', 'ISO standards corpus', 'admin-iso');
    else if (r === '/admin/samples') app.innerHTML = pageAdminCorpus('samples', 'Sample reports', 'admin-samples');
    else if (r === '/admin/templates') app.innerHTML = pageAdminCorpus('templates', 'Templates', 'admin-templates');
    else if (r === '/admin/instructions') app.innerHTML = pageAdminInstructions();
    else if (r === '/admin/settings') app.innerHTML = pageAdminSettings();
    else app.innerHTML = shell('projects', '<h1>Not found</h1><a href="#/projects">Home</a>');
  }

  window.MockUI = {
    login() { state.loggedIn = true; nav('/projects'); },
    logout() { state.loggedIn = false; nav('/login'); },
    setLang(l) { state.lang = l; render(); },
    openProject(id) { state.projectId = id; state.projectTab = 'mapping'; nav('/project/' + id); },
    setTab(tab) { state.projectTab = tab; render(); },
    selectFinding(id) { state.selectedFinding = id; render(); },
    setIsoClause(id) { state.isoClause = id; render(); },
    setIsoLang(l) { state.isoLang = l; render(); },
  };

  window.addEventListener('hashchange', render);
  if (!location.hash) location.hash = '#/login';
  render();
})();
