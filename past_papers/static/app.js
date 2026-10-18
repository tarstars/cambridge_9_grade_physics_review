'use strict';

const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const collectionNames = {all:'All practice papers',yearly:'Yearly exams',topical:'Topical practice',solutions:'Worked solutions',resources:'Reference files'};
const shortPapers = {'1':'Multiple choice','2':'AS structured','3':'Practical skills','4':'A Level structured','5':'Planning & analysis','6':'Legacy paper 6'};
const statusLabels = {unmarked:'Not marked',to_process:'To process',know_how:'Know how to solve',solved:'Solved'};
const initial = new URLSearchParams(location.hash.slice(1));
const filters = {collection:initial.get('collection') || 'all',paper:initial.get('paper') || '',year:initial.get('year') || '',session:initial.get('session') || '',status:initial.get('status') || '',q:initial.get('q') || '',group:initial.get('group') || 'year'};
if (!collectionNames[filters.collection]) filters.collection = 'all';
if (!['year','paper','session','folder'].includes(filters.group)) filters.group = 'year';
let library, state = {test:{},group:{}}, limit = 80, selected = new Set(), currentGroups = new Map(), detailTarget, toastTimer, searchTimer, busy = false;

async function request(url, options) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { throw new Error('The backend returned an unreadable response.'); }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  const node = $('#toast');
  node.textContent = message;
  node.classList.toggle('error', error);
  node.setAttribute('role', error ? 'alert' : 'status');
  node.hidden = false;
  toastTimer = setTimeout(() => node.hidden = true, error ? 8000 : 3500);
}

function statusOf(kind, id) { return state[kind][id]?.status || 'unmarked'; }
function notesOf(kind, id) { return state[kind][id]?.notes || ''; }
function options(status, placeholder) {
  return (placeholder ? `<option value="">${esc(placeholder)}</option>` : '') + Object.entries(statusLabels).map(([value,label]) => `<option value="${value}" ${value===status?'selected':''}>${esc(label)}</option>`).join('');
}
function selectMark(kind, id, label) {
  const status = statusOf(kind,id);
  return `<select class="status-select ${status}" data-mark="${kind}" data-id="${esc(id)}" aria-label="${esc(label)}">${options(status)}</select>`;
}
function fileLink(id, label, primary=false) {
  const file = library.files[id];
  if (!file) return '';
  const url = file.available ? `/files/${id}` : file.url;
  return `<a class="pdf-link ${primary?'primary':''}" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="${esc(file.filename)}${file.available?' · downloaded':file.error?' · unavailable at the last source download':' · opens PapaCambridge'}">${esc(label)} <span aria-hidden="true">↗</span>${file.available?'':`<small class="link-note">${file.error?'unavailable':'online'}</small>`}</a>`;
}

function renderNav() {
  const counts = Object.fromEntries(Object.keys(collectionNames).map(key => [key, key==='all'?library.tests.length:key==='resources'?library.resources.length:library.tests.filter(t=>t.collection===key).length]));
  const symbols = {all:'▤',yearly:'▦',topical:'◈',solutions:'✧',resources:'≡'};
  $('#collections').innerHTML = Object.entries(collectionNames).map(([key,name]) => `<button class="nav-button ${filters.collection===key&&!filters.paper?'active':''}" data-collection="${key}" ${filters.collection===key&&!filters.paper?'aria-current="page"':''}><span class="nav-symbol" aria-hidden="true">${symbols[key]}</span>${esc(name)}<span class="count">${counts[key]}</span></button>`).join('');
  $('#paper-nav').innerHTML = Object.entries(shortPapers).filter(([key]) => library.tests.some(t=>t.component===key)).map(([key,name]) => `<button class="nav-button ${filters.paper===key?'active':''}" data-paper="${key}" ${filters.paper===key?'aria-current="page"':''}><span class="nav-number">${key}</span>${esc(name)}<span class="count">${library.tests.filter(t=>t.component===key).length}</span></button>`).join('');
}

function renderStats() {
  const total=library.tests.length;
  const counts = Object.fromEntries(Object.keys(statusLabels).map(s=>[s,library.tests.filter(t=>statusOf('test',t.id)===s).length]));
  $('#stats').innerHTML = `<div class="stat"><span class="stat-label">YOUR PRACTICE LIBRARY</span><strong class="stat-value">${total.toLocaleString()}</strong><span class="stat-foot">Exam papers & topical practice</span></div>` + [
    ['solved','SOLVED','Completed, one paper at a time'],['know_how','KNOW HOW TO SOLVE','An approach you feel confident in'],['to_process','TO PROCESS','Your next practice sessions']
  ].map(([key,label,foot])=>`<div class="stat"><span class="stat-label"><i class="status-dot ${key}"></i>${label}</span><strong class="stat-value">${counts[key].toLocaleString()}</strong><span class="stat-foot">${foot}</span></div>`).join('');
  const files=Object.values(library.files), downloaded=files.filter(f=>f.available).length;
  $('#download-count').textContent = `${downloaded.toLocaleString()} of ${files.length.toLocaleString()} PDFs downloaded`;
  $('#download-meter').style.width = `${files.length?downloaded/files.length*100:0}%`;
  const date=library.synced_at?new Date(library.synced_at).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}):'Not synced yet';
  $('#catalogue-date').textContent=`Catalogue updated ${date}`;
}

function matchesBase(test) {
  if (filters.collection!=='all' && filters.collection!=='resources' && test.collection!==filters.collection) return false;
  if (filters.paper && test.component!==filters.paper) return false;
  if (filters.year && String(test.year)!==filters.year) return false;
  if (filters.session && test.session!==filters.session) return false;
  const text = [test.title,test.filename,test.folder,test.folder_path?.join(' '),test.year,library.sessions[test.session],test.component?`Paper ${test.component} ${library.papers[test.component]}`:'',notesOf('test',test.id)].join(' ').toLowerCase();
  return filters.q.toLowerCase().split(/\s+/).every(term=>text.includes(term));
}

function groupFor(test) {
  const fallback = {id:test.groups?.find(g=>g.startsWith('folder:')) || `folder:${test.folder_url}`,title:test.folder};
  if (filters.group==='year' && test.year) return {id:`year:${test.year}`,title:String(test.year)};
  if (filters.group==='paper' && test.component) return {id:`paper:${test.component}`,title:`Paper ${test.component} · ${library.papers[test.component] || 'Legacy paper'}`};
  if (filters.group==='session' && test.year && test.session) return {id:`session:${test.year}:${test.session}`,title:`${library.sessions[test.session]} ${test.year}`};
  return fallback;
}

function renderRow(test, reference=false) {
  const title = test.kind==='qp' ? (library.papers[test.component] || test.title) : test.title;
  const subtitle = test.kind==='qp' ? `${library.sessions[test.session]} ${test.year}<span class="separator">·</span>9702/${esc(test.variant)}` : esc(test.folder);
  const note = notesOf('test',test.id);
  const scheme = test.attachments?.find(a=>a.kind==='ms');
  return `<article class="paper-row">${reference?'<span></span>':`<input class="paper-check" type="checkbox" data-select="${test.id}" aria-label="Select ${esc(test.filename)}" ${selected.has(test.id)?'checked':''}>`}<div class="paper-badge ${test.collection}" aria-hidden="true">${test.component || (reference?'↗':'◈')}<small>${reference?'FILE':test.component?'PAPER':'TOPIC'}</small></div><div class="paper-main">${reference?`<span class="paper-title">${esc(library.kinds[test.kind] || title)}</span>`:`<button class="paper-title" data-notes="test" data-id="${test.id}">${esc(title)}</button>`}<div class="paper-meta">${subtitle}${test.kind==='qp'?`<span class="separator">·</span>Paper ${esc(test.variant)}`:''}</div>${note?`<span class="row-note-preview">${esc(note)}</span>`:''}</div><div class="paper-links">${fileLink(test.id,reference?'Open PDF':test.kind==='qp'?'Paper':'Practice',true)}${scheme?fileLink(scheme.id,'Mark scheme'):''}</div><div class="row-status">${reference?`<span class="muted">${esc(test.filename)}</span>`:selectMark('test',test.id,`Study status for ${test.filename}`)}</div>${reference?'<span></span>':`<button class="notes-button ${note?'has-note':''}" data-notes="test" data-id="${test.id}" aria-label="${note?'Edit':'Add'} notes for ${esc(test.filename)}" title="${note?'Edit':'Add'} notes">▱</button>`}</article>`;
}

function renderResults() {
  if (!library) return;
  const reference=filters.collection==='resources';
  const base=(reference?library.resources:library.tests).filter(matchesBase);
  const filtered=base.filter(t=>reference||!filters.status||statusOf('test',t.id)===filters.status);
  filtered.sort((a,b)=>(b.year||0)-(a.year||0) || ({w:3,s:2,m:1}[b.session]||0)-({w:3,s:2,m:1}[a.session]||0) || String(a.component||'').localeCompare(String(b.component||''),undefined,{numeric:true}) || a.filename.localeCompare(b.filename,undefined,{numeric:true}));
  const title=filters.paper?`Paper ${filters.paper} · ${library.papers[filters.paper] || 'Physics'}`:collectionNames[filters.collection];
  $('#library-title').textContent=title;
  $('#result-count').textContent=`${filtered.length.toLocaleString()} ${reference?'reference files':'practice papers'}${filters.q||filters.year||filters.session||filters.status?' match your filters':' in your collection'}`;
  $('#status-tabs').hidden=reference;
  $('#status-tabs').innerHTML=[['','All papers'],...Object.entries(statusLabels)].map(([key,label])=>`<button class="status-tab ${filters.status===key?'active':''}" data-status="${key}" aria-pressed="${filters.status===key}">${esc(label)}<span>${key?base.filter(t=>statusOf('test',t.id)===key).length:base.length}</span></button>`).join('');
  const warnings=[];
  if (reference) warnings.push('Supporting documents for your exams. Reference files do not affect your study progress.');
  if (library.index_errors.length) warnings.push(`${library.index_errors.length} source folders could not be indexed. Run the sync command again to retry.`);
  const unavailable=Object.values(library.files).filter(file=>file.error).length;
  if (unavailable) warnings.push(`${unavailable} ${unavailable===1?'PDF was':'PDFs were'} unavailable at the source. These files are labelled unavailable; run the sync command again to retry.`);
  if (library.tests.length===0) warnings.push('Build the catalogue with: python3 -m past_papers.sync');
  $('#filter-note').textContent=warnings.join(' ');
  $('#filter-note').hidden=!warnings.length;
  currentGroups=new Map();
  for (const test of filtered) {
    const group=groupFor(test);
    if (!currentGroups.has(group.id)) currentGroups.set(group.id,{...group,tests:[]});
    currentGroups.get(group.id).tests.push(test);
  }
  let rendered=0;
  const html=[];
  for (const group of currentGroups.values()) {
    if (rendered>=limit) break;
    const shown=group.tests.slice(0,limit-rendered);
    rendered+=shown.length;
    const solved=group.tests.filter(t=>statusOf('test',t.id)==='solved').length;
    html.push(`<section class="paper-group" aria-label="${esc(group.title)}"><div class="group-heading"><div class="group-label"><h3>${esc(group.title)}</h3><span>${group.tests.length} ${reference?'files':'papers'}${reference?'':` · ${solved} solved`}</span></div>${reference?'':`<div class="group-actions"><button class="group-note-button" data-notes="group" data-id="${esc(group.id)}" aria-label="Notes for group ${esc(group.title)}">${notesOf('group',group.id)?'▱ Notes':'＋ Notes'}</button><label><span>Group mark</span>${selectMark('group',group.id,`Group mark for ${group.title}`)}</label><select class="group-bulk" data-group-bulk="${esc(group.id)}" aria-label="Mark all ${group.tests.length} filtered papers in ${esc(group.title)}">${options('',`Mark all ${group.tests.length} papers…`)}</select></div>`}</div><div class="group-rows">${shown.map(t=>renderRow(t,reference)).join('')}</div></section>`);
  }
  $('#papers').innerHTML=html.join('') || `<div class="empty"><span class="empty-symbol" aria-hidden="true">◈</span><h3>${library.tests.length?'A fresh page awaits.':'Your library starts here.'}</h3><p>${library.tests.length?'No papers match these filters. Try another year, topic, or study status.':'Run the sync command to discover and download Physics 9702 papers.'}</p>${library.tests.length?'<button class="quiet-button" data-reset>Clear filters</button>':'<code>python3 -m past_papers.sync</code>'}</div>`;
  $('#papers').setAttribute('aria-busy','false');
  $('#show-more').hidden=rendered>=filtered.length;
  $('#show-more').textContent=`Show ${Math.min(80,filtered.length-rendered)} more papers ↓ (${filtered.length-rendered} remaining)`;
  renderSelection();
}

function renderSelection() {
  $('#bulk-bar').hidden=selected.size===0;
  $('#selection-count').textContent=`${selected.size} selected`;
}

function render() { renderNav(); renderStats(); renderResults(); }

function setFilters(changes) {
  Object.assign(filters,changes);
  selected.clear(); limit=80;
  $('#search').value=filters.q;
  $('#year').value=filters.year;
  $('#session').value=filters.session;
  $('#group-by').value=filters.group;
  $('#paper-filter').value=filters.paper;
  const params=new URLSearchParams(Object.entries(filters).filter(([key,val])=>val && !(key==='collection'&&val==='all') && !(key==='group'&&val==='year')));
  history.replaceState(null,'',location.pathname+(params.size?'#'+params:''));
  renderNav(); renderResults();
}
function resetFilters() { setFilters({collection:'all',paper:'',year:'',session:'',status:'',q:'',group:'year'}); }

async function save(updates,message='Progress saved') {
  if (busy) { renderResults(); toast('Please wait for the current save to finish.'); return false; }
  busy=true;
  let saved=false;
  $('#restore-button').disabled=true;
  $('#save-state').textContent='Saving progress…';
  try {
    state=await request('/api/marks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({updates})});
    selected.clear(); render(); toast(message); saved=true;
    return true;
  } catch(error) { render(); toast(`Progress was not saved: ${error.message}`,true); return false; }
  finally { busy=false; $('#restore-button').disabled=false; $('#save-state').innerHTML=saved?'<span class="small-dot"></span> Progress saved locally':'Save failed — please retry'; }
}

function openNotes(kind,id) {
  const test=library.tests.find(t=>t.id===id);
  const group=currentGroups.get(id);
  if (kind==='test'&&!test || kind==='group'&&!group) return;
  detailTarget={kind,id};
  $('#details-eyebrow').textContent=kind==='group'?'GROUP NOTES':'PAPER NOTES';
  $('#details-title').textContent=kind==='group'?group.title:test.kind==='qp'?`${library.papers[test.component] || test.title} · Paper ${test.variant}`:test.title;
  $('#details-subtitle').textContent=kind==='group'?'A separate mark for this group. Individual papers keep their own marks.':test.filename;
  $('#detail-status').innerHTML=options(statusOf(kind,id));
  $('#notes').value=notesOf(kind,id);
  $('#notes-message').textContent='Saved locally with your study progress.';
  $('#details-files').innerHTML=kind==='group'?'':[{id:test.id,label:test.kind==='qp'?'Question paper':'Practice PDF'},...(test.attachments||[])].map(file=>`<div class="details-file"><span>${esc(file.label)}<br><small>${esc(library.files[file.id]?.filename)}</small></span>${fileLink(file.id,'Open PDF')}</div>`).join('');
  $('#details-dialog').showModal();
}

document.addEventListener('click',event=>{
  const collection=event.target.closest('[data-collection]');
  if (collection) setFilters({collection:collection.dataset.collection,paper:'',year:'',session:'',q:'',status:'',group:['topical','solutions'].includes(collection.dataset.collection)?'folder':'year'});
  const paper=event.target.closest('[data-paper]');
  if (paper) setFilters({collection:'all',paper:paper.dataset.paper,q:'',status:'',year:'',session:''});
  const tab=event.target.closest('[data-status]');
  if (tab) setFilters({status:tab.dataset.status});
  const notes=event.target.closest('[data-notes]');
  if (notes) openNotes(notes.dataset.notes,notes.dataset.id);
  const close=event.target.closest('[data-close]');
  if (close) close.closest('dialog').close();
  if (event.target.closest('[data-reset]')) resetFilters();
});

document.addEventListener('change',async event=>{
  const target=event.target;
  if (target.matches('[data-mark]')) {
    target.disabled=true;
    await save([{kind:target.dataset.mark,id:target.dataset.id,status:target.value}]);
  }
  if (target.matches('[data-select]')) {
    if (target.checked) selected.add(target.dataset.select); else selected.delete(target.dataset.select);
    renderSelection();
  }
  if (target.matches('[data-group-bulk]')&&target.value) {
    const group=currentGroups.get(target.dataset.groupBulk);
    const status=target.value;
    target.disabled=true;
    await save(group.tests.map(t=>({kind:'test',id:t.id,status})),`${group.tests.length} papers marked ${statusLabels[status].toLowerCase()}`);
  }
});

$('#search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>setFilters({q:$('#search').value}),160);});
$('#year').addEventListener('change',()=>setFilters({year:$('#year').value}));
$('#session').addEventListener('change',()=>setFilters({session:$('#session').value}));
$('#group-by').addEventListener('change',()=>setFilters({group:$('#group-by').value}));
$('#reset-filters').addEventListener('click',resetFilters);
$('#show-more').addEventListener('click',()=>{limit+=80;renderResults();});
$('#clear-selection').addEventListener('click',()=>{selected.clear();renderResults();});
$('#bulk-apply').addEventListener('click',async()=>{
  const button=$('#bulk-apply');button.disabled=true;
  await save([...selected].map(id=>({kind:'test',id,status:$('#bulk-status').value})),`${selected.size} papers updated`);
  button.disabled=false;
});
$('#notes-form').addEventListener('submit',async event=>{
  event.preventDefault();
  $('#save-notes').disabled=true;
  const success=await save([{...detailTarget,status:$('#detail-status').value,notes:$('#notes').value}]);
  $('#save-notes').disabled=false;
  if (success) $('#details-dialog').close();
  else $('#notes-message').textContent='Could not save. Your text is still here; please try again.';
});
$('#about-button').addEventListener('click',()=>$('#about-dialog').showModal());
$('#footer-help').addEventListener('click',()=>$('#about-dialog').showModal());
$('#restore-button').addEventListener('click',()=>$('#restore-file').click());
$('#restore-file').addEventListener('change',async event=>{
  const file=event.target.files[0]; if (!file) return;
  if (busy) { event.target.value='';toast('Please wait for the current save to finish.');return; }
  busy=true;
  try {
    if (file.size>20_000_000) throw new Error('Backup exceeds 20 MB.');
    const backup=JSON.parse(await file.text());
    state=await request('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(backup)});
    render();toast('Progress restored from your backup');
  } catch(error) { toast(`Could not restore: ${error.message}`,true); }
  finally {busy=false;event.target.value='';}
});

async function start() {
  try {
    [library,state]=await Promise.all([request('/api/library'),request('/api/state')]);
    const years=[...new Set(library.tests.concat(library.resources).map(t=>t.year).filter(Boolean))].sort((a,b)=>b-a);
    $('#year').innerHTML='<option value="">All years</option>'+years.map(y=>`<option>${y}</option>`).join('');
    const label=document.createElement('label');label.className='paper-filter-label';
    label.innerHTML='<span class="sr-only">Paper type</span><select id="paper-filter"><option value="">All paper types</option>'+Object.entries(shortPapers).map(([id,name])=>`<option value="${id}">P${id} · ${esc(name)}</option>`).join('')+'</select>';
    $('.filters').insertBefore(label,$('#reset-filters'));
    $('#paper-filter').addEventListener('change',()=>setFilters({paper:$('#paper-filter').value}));
    setFilters({});renderStats();
    setInterval(async()=>{
      if (document.hidden||$('dialog[open]')||busy||selected.size) return;
      try {library=await request('/api/library');state=await request('/api/state');renderStats();renderResults();} catch { /* Keep the last successful view if the backend stops. */ }
    },30000);
  } catch(error) {
    $('#papers').setAttribute('aria-busy','false');
    $('#papers').innerHTML=`<div class="empty"><h3>Could not open your library.</h3><p>${esc(error.message)}<br>Start the backend with <code>python3 -m past_papers.server</code>, then reload.</p><button class="quiet-button" id="retry">Try again</button></div>`;
    $('#retry').addEventListener('click',()=>location.reload());
    toast('Could not connect to the Python backend.',true);
  }
}
start();
