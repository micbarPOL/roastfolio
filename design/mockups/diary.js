(() => {
  const byId = id => document.getElementById(id);
  const icons = () => window.lucide?.createIcons();
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const sampleNotes = [
    {note_id:'d-001',title:'Apple',ticker:'AAPL',is_active:true,updatedAt:'2026-11-02T15:40:00Z',note_text:'Added on the pullback, not because the chart looked exciting. Services growth is the reason I am still here. @AAPL',user_tags:['#long-term','#earnings'],hypothesis:{why_buy:'Installed base and recurring services revenue keep compounding.',exit_plan:'Revisit if services growth slows for two consecutive reports.',risk_factors:'Valuation assumes durable margins and steady buybacks.'},comments:[{text:'Wait for the report. No averaging up before the call.',created_at:'2026-11-02T15:40:00Z'}],checklist:[{text:'Read the next 10-Q services breakdown',due_date:'2026-11-10',checked:false},{text:'Compare gross margin to prior quarter',due_date:'2026-10-28',checked:false}]},
    {note_id:'d-002',title:'Microsoft',ticker:'MSFT',is_active:true,updatedAt:'2026-10-31T09:10:00Z',note_text:'Cloud thesis intact. The position is already large enough; let the evidence catch up.',user_tags:['#thesis','#risk'],hypothesis:{why_buy:'Azure demand and durable enterprise distribution.',exit_plan:'Reassess if cloud growth decelerates materially.',risk_factors:'AI capex may not earn its cost of capital.'},comments:[],checklist:[{text:'Review Azure growth and capex together',due_date:'2026-11-18',checked:true}]},
    {note_id:'d-003',title:'ASML',ticker:'ASML',is_active:true,updatedAt:'2026-10-25T13:25:00Z',note_text:'Cyclical demand is still lumpy. Long horizon, short patience.',user_tags:['#semiconductors','#long-term'],hypothesis:{why_buy:'Critical lithography bottleneck with a durable moat.',exit_plan:'Review export controls and order cancellations.',risk_factors:'Customer concentration and geopolitics.'},comments:[{text:'Do not confuse backlog with delivered revenue.',created_at:'2026-10-26T08:30:00Z'}],checklist:[{text:'Check order intake after earnings',due_date:'2026-11-13',checked:false}]},
    {note_id:'d-004',title:'ARKK',ticker:'ARKK',is_active:false,updatedAt:'2026-09-14T16:05:00Z',note_text:'Closed. Growth duration was longer than my risk budget. Keep this as a process note, not a watchlist.',user_tags:['#closed','#lesson'],hypothesis:{why_buy:'Expected a faster return to profitable growth.',exit_plan:'Closed after thesis timing broke.',risk_factors:'Duration risk, concentrated holdings and expensive capital.'},comments:[],checklist:[{text:'Write down what would invalidate this sooner next time',due_date:'2026-09-21',checked:true}]}
  ];
  const state={notes:location.search.includes('state=empty')?[]:sampleNotes.map(note=>structuredClone(note)),selected:'d-001',filter:'',tag:'',onlyOpen:false,composerOpen:false};
  const dateLabel=value=>value?new Date(`${String(value).slice(0,10)}T12:00:00`).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}):'';
  const statusOf=note=>note.is_active?'Active thesis':'Archived';
  const tagsOf=note=>Array.isArray(note.user_tags)?note.user_tags:[];
  const checksOf=note=>Array.isArray(note.checklist)?note.checklist:[];
  const openCount=note=>checksOf(note).filter(item=>!item.checked).length;
  const mentionsOf=note=>[...new Set((String(note.note_text||'').match(/@[A-Za-z0-9][A-Za-z0-9._-]{0,19}/g)||[]).map(value=>value.slice(1).toUpperCase()))];
  const orderedNotes=()=>state.notes.slice().sort((a,b)=>Number(b.is_active)-Number(a.is_active)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));

  function filteredNotes(){
    const query=state.filter.trim().toLocaleLowerCase();
    return orderedNotes().filter(note=>{
      const haystack=[note.title,note.ticker,note.note_text,...tagsOf(note),...Object.values(note.hypothesis||{})].join(' ').toLocaleLowerCase();
      return (!query||haystack.includes(query))&&(!state.tag||tagsOf(note).includes(state.tag))&&(!state.onlyOpen||openCount(note)>0);
    });
  }
  function renderTags(){
    const counts=new Map();state.notes.forEach(note=>tagsOf(note).forEach(tag=>counts.set(tag,(counts.get(tag)||0)+1)));
    byId('tag-filters').innerHTML=[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([tag,count])=>`<button type="button" data-tag="${escape(tag)}" aria-pressed="${state.tag===tag}">${escape(tag)} <span>${count}</span></button>`).join('');
    byId('tag-filters').querySelectorAll('[data-tag]').forEach(button=>button.addEventListener('click',()=>{state.tag=state.tag===button.dataset.tag?'':button.dataset.tag;render();}));
    byId('clear-ledger-filter').hidden=!(state.filter||state.tag||state.onlyOpen);
  }
  function renderLedger(){
    const notes=filteredNotes();
    if(!notes.some(note=>note.note_id===state.selected))state.selected=notes[0]?.note_id||'';
    byId('ledger-count').textContent=`${notes.length} of ${state.notes.length} notes`;
    byId('note-ledger').innerHTML=notes.map(note=>{
      const selected=note.note_id===state.selected;
      const tagList=tagsOf(note).slice(0,3).map(tag=>`<span class="d-tag">${escape(tag)}</span>`).join('');
      return `<button type="button" class="d-note-row${note.is_active?'':' is-inactive'}" data-note-id="${escape(note.note_id)}" aria-current="${selected}" aria-label="${escape(note.title||note.ticker)}, ${statusOf(note)}, ${openCount(note)} open checkpoints">
        <span class="d-note-row-top"><span class="d-note-row-title">${escape(note.title||note.ticker||'Untitled note')}</span><span class="d-status ${note.is_active?'is-active':'is-inactive'}">${statusOf(note)}</span></span>
        <span class="d-note-row-preview">${escape(note.note_text||'No note yet')}</span>
        <span class="d-note-row-meta"><span class="num">${escape(note.ticker||'—')}</span><span>${dateLabel(note.updatedAt)}</span><span class="d-open-count">${openCount(note)} open</span></span>
        <span class="d-note-row-tags">${tagList}</span>
      </button>`;
    }).join('');
    byId('diary-ledger-empty').hidden=notes.length>0;
    byId('note-ledger').hidden=notes.length===0;
    byId('note-ledger').querySelectorAll('[data-note-id]').forEach(button=>button.addEventListener('click',()=>selectNote(button.dataset.noteId)));
  }
  function renderFocus(){
    const note=state.notes.find(item=>item.note_id===state.selected);
    byId('focus-empty').hidden=Boolean(note);
    byId('focus-content').hidden=!note;
    if(!note){document.querySelector('.d-focus').dataset.mobileOpen='false';return;}
    document.querySelector('.d-focus').dataset.mobileOpen=String(state.mobileOpen||false);
    byId('focus-ticker').textContent=note.ticker||'Untickered note';
    byId('focus-title').textContent=note.title||note.ticker||'Untitled note';
    byId('focus-tags').innerHTML=tagsOf(note).map(tag=>`<span class="d-tag">${escape(tag)}</span>`).join('');
    byId('focus-status').textContent=statusOf(note);
    byId('focus-status').className=`d-status ${note.is_active?'is-active':'is-inactive'}`;
    byId('toggle-active').textContent=note.is_active?'Mark inactive':'Reactivate thesis';
    byId('toggle-active').setAttribute('aria-pressed',String(note.is_active));
    byId('note-updated').textContent=`Updated ${dateLabel(note.updatedAt)}`;
    byId('note-text').value=note.note_text||'';
    byId('why-buy').value=note.hypothesis?.why_buy||'';
    byId('exit-plan').value=note.hypothesis?.exit_plan||'';
    byId('risk-factors').value=note.hypothesis?.risk_factors||'';
    byId('note-mentions').innerHTML=mentionsOf(note).map(ticker=>`<button type="button" class="d-mention" data-mention="${escape(ticker)}"><i data-lucide="chart-no-axes-combined" aria-hidden="true"></i>@${escape(ticker)} <span>View analysis</span></button>`).join('')||'<span class="d-muted">No linked assets in this note.</span>';
    const checklist=checksOf(note);
    byId('checklist-count').textContent=`${checklist.filter(item=>!item.checked).length} open · ${checklist.length} total`;
    byId('checklist-items').innerHTML=checklist.map((item,index)=>`<label class="d-check-item"><input type="checkbox" data-check="${index}" ${item.checked?'checked':''}><span class="d-check-copy ${item.checked?'is-complete':''}">${escape(item.text)}</span><span class="d-check-due ${!item.checked&&item.due_date<'2026-11-03'?'is-overdue':''}">${escape(dateLabel(item.due_date)||'No due date')}</span></label>`).join('')||'<p class="d-muted">No review checkpoints yet.</p>';
    byId('comment-count').textContent=`${(note.comments||[]).length} entries`;
    byId('comment-list').innerHTML=(note.comments||[]).map(comment=>`<article class="d-comment"><div class="d-comment-meta"><span>Observation</span><time>${escape(dateLabel(comment.created_at))}</time></div><p>${escape(comment.text)}</p></article>`).join('')||'<p class="d-muted">Add an observation when new information arrives.</p>';
    icons();
  }
  function render(){renderTags();renderLedger();renderFocus();icons();}
  function selectNote(id){state.selected=id;state.mobileOpen=true;renderLedger();renderFocus();}
  function openComposer(){state.composerOpen=true;byId('composer-backdrop').hidden=false;byId('note-composer').classList.add('is-open');byId('note-composer').setAttribute('aria-hidden','false');setTimeout(()=>byId('composer-ticker').focus(),20);}
  function closeComposer(){state.composerOpen=false;byId('composer-backdrop').hidden=true;byId('note-composer').classList.remove('is-open');byId('note-composer').setAttribute('aria-hidden','true');byId('new-note').focus();}
  const announce=message=>{byId('diary-announcement').textContent=message;};
  byId('ledger-search').addEventListener('input',event=>{state.filter=event.target.value;render();});
  byId('only-open-checklist').addEventListener('change',event=>{state.onlyOpen=event.target.checked;render();});
  byId('clear-ledger-filter').addEventListener('click',()=>{state.filter='';state.tag='';state.onlyOpen=false;byId('ledger-search').value='';byId('only-open-checklist').checked=false;render();});
  byId('empty-clear').addEventListener('click',()=>byId('clear-ledger-filter').click());
  document.querySelectorAll('#new-note,#mobile-new-note,#focus-empty-new').forEach(button=>button.addEventListener('click',openComposer));
  byId('composer-close').addEventListener('click',closeComposer);
  byId('composer-backdrop').addEventListener('click',closeComposer);
  byId('composer-form').addEventListener('submit',event=>{
    event.preventDefault();const ticker=byId('composer-ticker').value.trim();const text=byId('composer-text').value.trim();
    if(!ticker){byId('composer-error').textContent='Add a ticker or decision topic.';byId('composer-error').hidden=false;return;}
    if(!text){byId('composer-error').textContent='Write a note before creating the entry.';byId('composer-error').hidden=false;return;}
    const note={note_id:`sample-${Date.now()}`,title:ticker,ticker:ticker.replace(/^@/, '').toUpperCase(),is_active:true,updatedAt:new Date().toISOString(),note_text:text,user_tags:[...new Set(text.match(/#[A-Za-z0-9_.$:-]+/g)||[])],hypothesis:{why_buy:'',exit_plan:'',risk_factors:''},comments:[],checklist:[]};
    state.notes.unshift(note);state.selected=note.note_id;state.filter='';state.tag='';state.onlyOpen=false;byId('ledger-search').value='';byId('only-open-checklist').checked=false;byId('composer-form').reset();closeComposer();render();announce('Sample note created.');
  });
  byId('note-text').addEventListener('input',()=>{const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;note.note_text=byId('note-text').value;note.user_tags=[...new Set(note.note_text.match(/#[A-Za-z0-9_.$:-]+/g)||[])];note.updatedAt=new Date().toISOString();byId('focus-tags').innerHTML=tagsOf(note).map(tag=>`<span class="d-tag">${escape(tag)}</span>`).join('');byId('note-mentions').innerHTML=mentionsOf(note).map(ticker=>`<button type="button" class="d-mention" data-mention="${escape(ticker)}"><i data-lucide="chart-no-axes-combined" aria-hidden="true"></i>@${escape(ticker)} <span>View analysis</span></button>`).join('')||'<span class="d-muted">No linked assets in this note.</span>';byId('note-updated').textContent=`Updated ${dateLabel(note.updatedAt)}`;renderLedger();icons();});
  byId('save-note').addEventListener('click',()=>{const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;note.note_text=byId('note-text').value;note.user_tags=[...new Set(note.note_text.match(/#[A-Za-z0-9_.$:-]+/g)||[])];note.updatedAt=new Date().toISOString();render();announce('Sample note saved.');});
  byId('save-thesis').addEventListener('click',()=>{const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;note.hypothesis={why_buy:byId('why-buy').value,exit_plan:byId('exit-plan').value,risk_factors:byId('risk-factors').value};note.updatedAt=new Date().toISOString();renderLedger();byId('note-updated').textContent=`Updated ${dateLabel(note.updatedAt)}`;announce('Sample thesis saved.');});
  byId('toggle-active').addEventListener('click',()=>{const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;note.is_active=!note.is_active;note.updatedAt=new Date().toISOString();render();announce(note.is_active?'Thesis reactivated.':'Thesis archived.');});
  byId('delete-note').addEventListener('click',()=>{const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;if(window.confirm(`Delete the sample note “${note.title}”?`)){state.notes=state.notes.filter(item=>item.note_id!==state.selected);state.selected='';render();}});
  byId('checklist-items').addEventListener('change',event=>{if(!event.target.matches('[data-check]'))return;const note=state.notes.find(item=>item.note_id===state.selected);if(!note)return;note.checklist[Number(event.target.dataset.check)].checked=event.target.checked;render();});
  byId('add-check-form').addEventListener('submit',event=>{event.preventDefault();const note=state.notes.find(item=>item.note_id===state.selected);const text=byId('new-check-text').value.trim();if(!note||!text)return;note.checklist.push({text,due_date:byId('new-check-date').value,checked:false});byId('add-check-form').reset();renderFocus();renderLedger();});
  byId('add-comment-form').addEventListener('submit',event=>{event.preventDefault();const note=state.notes.find(item=>item.note_id===state.selected);const text=byId('new-comment').value.trim();if(!note||!text)return;note.comments=note.comments||[];note.comments.push({text,created_at:new Date().toISOString()});byId('new-comment').value='';renderFocus();announce('Observation added.');});
  byId('note-mentions').addEventListener('click',event=>{const link=event.target.closest('[data-mention]');if(link)announce(`Open asset analysis for ${link.dataset.mention} in the live application.`);});
  byId('mobile-back').addEventListener('click',()=>{state.mobileOpen=false;document.querySelector('.d-focus').dataset.mobileOpen='false';byId('ledger-search').focus();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(state.composerOpen)closeComposer();}});
  document.querySelectorAll('[data-theme-choice]').forEach(button=>button.addEventListener('click',()=>{document.documentElement.dataset.theme=button.dataset.themeChoice;document.querySelectorAll('[data-theme-choice]').forEach(item=>item.setAttribute('aria-pressed',String(item.dataset.themeChoice===button.dataset.themeChoice)));}));
  document.querySelector('.d-mobile-theme').addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;document.querySelectorAll('[data-theme-choice]').forEach(item=>item.setAttribute('aria-pressed',String(item.dataset.themeChoice===theme)));});
  document.querySelector('.sidebar-collapse').addEventListener('click',event=>{const collapsed=document.querySelector('.app').dataset.sidebar!=='collapsed';document.querySelector('.app').dataset.sidebar=collapsed?'collapsed':'expanded';event.currentTarget.setAttribute('aria-pressed',String(collapsed));});
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(link=>{const clone=link.cloneNode(true);clone.removeAttribute('data-field');byId('diary-menu-links').append(clone);});
  const menu=byId('diary-menu');document.querySelector('.d-menu').addEventListener('click',()=>{menu.showModal();document.querySelector('.d-menu').setAttribute('aria-expanded','true');});byId('menu-close').addEventListener('click',()=>menu.close());menu.addEventListener('close',()=>document.querySelector('.d-menu').setAttribute('aria-expanded','false'));
  const params=new URLSearchParams(location.search);document.documentElement.dataset.theme=params.get('theme')==='light'?'light':'dark';
  if(params.get('state')==='loading'){byId('note-ledger').hidden=true;byId('focus-sheet').hidden=true;byId('diary-loading').hidden=false;}
  else render();
  window.diaryMockup={state,render,selectNote,filteredNotes};
})();