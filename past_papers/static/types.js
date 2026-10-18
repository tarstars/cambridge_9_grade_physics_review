'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => Number(value || 0).toLocaleString();
const statuses = {unmarked:'Not marked',to_process:'To process',know_how:'Know how to solve',solved:'Solved'};
const sessionNames = {m:'Feb / Mar',s:'May / June',w:'Oct / Nov'};
let state = {}, catalogue = null, taskResult = null, requestId = 0, toastTimer, searchTimer;
const options = selected => Object.entries(statuses).map(([key,label]) => `<option value="${key}" ${key===selected?'selected':''}>${label}</option>`).join('');
const query = () => Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
const typeById = key => catalogue?.types.find(type => type.id===key);
const topicById = key => catalogue?.topics.find(topic => topic.id===key);

async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Could not complete the request.');
  return result;
}
function toast(message, failure=false) {
  clearTimeout(toastTimer);
  $('#toast').textContent=message; $('#toast').hidden=false;
  $('#toast').style.background=failure?'#8a492e':'';
  toastTimer=setTimeout(()=>$('#toast').hidden=true, failure?9000:3500);
}
function navigate(changes, replace=false) {
  clearTimeout(searchTimer);
  const next={...state,...changes};
  const hash=new URLSearchParams(Object.entries(next).filter(([key,value])=>value && !(key==='page' && Number(value)===1)));
  if(replace){history.replaceState(null,'','#'+hash);state=query();render();}
  else if(location.hash.slice(1)===hash.toString()){state=query();render();}
  else location.hash=hash.toString();
}
function filters() {
  const result={};
  if(state.format==='structured')result.structured='1';
  else if(state.format)result.paper=state.format;
  return result;
}
function image(url, label, sample=false) {
  return `<img src="${esc(url)}?compact=1" alt="${esc(label)}" loading="lazy" decoding="async"><span class="${sample?'sample-fallback':'image-error'}">Preview unavailable. Open the source PDF to read this question.</span>`;
}
function renderNav() {
  const expanded=new Map([...document.querySelectorAll('.type-topic')].map(element=>[element.dataset.topic,element.open]));
  const current=typeById(state.type);
  $('#type-count').textContent=catalogue.types.filter(type=>type.total && type.id!=='unassigned').length;
  $('#type-nav').innerHTML=catalogue.topics.map(topic=>{
    const types=catalogue.types.filter(type=>type.topic===topic.id && type.total && type.id!=='unassigned');
    if(!types.length)return '';
    const open=expanded.get(topic.id)??(current?.topic===topic.id || state.topic===topic.id || (!state.type && topic.id==='units'));
    return `<details class="type-topic" data-topic="${topic.id}" ${open?'open':''}><summary>${esc(topic.label)}<span>${types.length}</span></summary>${types.map(type=>`<a href="#type=${type.id}${state.format?'&format='+esc(state.format):''}" class="type-nav-item ${state.type===type.id?'active':''}" ${state.type===type.id?'aria-current="page"':''}>${esc(type.label)}<span>${number(type.total)}</span></a>`).join('')}</details>`;
  }).join('')+`<a class="type-nav-item ${state.type==='unassigned'?'active':''}" href="#type=unassigned">Awaiting a task type <span>${number(catalogue.unassigned)}</span></a>`;
  const selected=$('#topic').value;
  $('#topic').innerHTML='<option value="">All syllabus topics</option>'+catalogue.topics.filter(topic=>catalogue.types.some(type=>type.topic===topic.id && type.total)).map(topic=>`<option value="${topic.id}">${esc(topic.label)}</option>`).join('');
  $('#topic').value=state.topic||selected||'';
}
function renderOverview() {
  const term=(state.q||'').toLowerCase().trim();
  const types=catalogue.types.filter(type=>type.total && type.id!=='unassigned' && (!state.topic || type.topic===state.topic)
    && (!state.type_status || type.status===state.type_status)
    && (!term || [type.label,type.approach,topicById(type.topic)?.label].join(' ').toLowerCase().includes(term)));
  $('#overview-title').textContent=state.topic?topicById(state.topic)?.label||'Task types':'Explore task types';
  $('#overview-count').textContent=`${types.length} specific patterns · open one to compare similar questions`;
  $('#type-cards').innerHTML=types.map(type=>`<article class="type-card" data-type="${type.id}">
    <a class="type-card-body" href="#type=${type.id}${state.format?'&format='+esc(state.format):''}"><div class="eyebrow">${esc(topicById(type.topic)?.label)}</div><h3>${esc(type.label)}</h3><p class="sample-label">${number(type.total)} questions using this approach</p></a>
    <a class="type-sample" href="#type=${type.id}${state.format?'&format='+esc(state.format):''}" aria-label="Practise ${esc(type.label)}">${image(type.sample.image,'Example: '+type.label,true)}</a>
    <div class="type-card-foot"><span class="type-mark ${esc(type.status)}"><span class="status-dot ${esc(type.status)}"></span>${esc(statuses[type.status])}</span><a class="type-open" href="#type=${type.id}${state.format?'&format='+esc(state.format):''}">Practise this type ↗</a></div></article>`).join('')||'<div class="empty-types">No task types match these filters.<br><button class="text-button" data-reset>Clear filters</button></div>';
  $('#type-cards').setAttribute('aria-busy','false');
  const unassigned=typeById('unassigned');
  $('#unassigned-notice').innerHTML=unassigned.total?`<div class="unassigned-notice"><strong>${number(unassigned.total)} questions await a specific task type.</strong> They remain available to read and classify. Assignments above are suggestions based on each question’s content.<br><a href="#type=unassigned${state.format?'&format='+esc(state.format):''}">Review unassigned questions →</a></div>`:'';
}
function source(task) {
  if(task.collection==='yearly')return `9702/${esc(task.filename.match(/_(?:qp|ms)_(\d+)/)?.[1]||task.component)} · ${esc(sessionNames[task.session]||'')} ${esc(task.year||'')}`;
  return esc(task.filename);
}
function taskCard(task) {
  const extra=task.task_types.filter(key=>key!==state.type);
  return `<article class="task-card ${task.component==='1'?'':'wide-task'}" data-id="${task.id}">
    <header class="task-card-header"><div class="task-source"><strong>Question ${task.number}</strong>${source(task)}<small>${task.collection==='yearly'?'Original exam question':'Topical collection'} · page ${task.page}${task.end_page>task.page?'–'+task.end_page:''}${task.subparts.length?' · subparts kept together':''}</small></div><label>This question<select class="status-select ${esc(task.status)}" data-question-status aria-label="Progress for question ${task.number}">${options(task.status)}</select></label></header>
    ${task.images.map((region,index)=>`${index?`<div class="region-label">Continuation · page ${region.page}</div>`:''}<button class="inline-original" data-zoom="${index}" aria-label="Enlarge question ${task.number}${index?' continuation':''}">${image(region.url,`Original question ${task.number}, page ${region.page}`)}</button>`).join('')}
    <div class="task-card-footer"><div class="task-actions"><a href="/files/${task.document_id}#page=${task.page}" target="_blank" rel="noopener">Source PDF ↗</a><button data-files>Answers & reference files ↗</button><span class="assignment-tag ${task.type_source==='confirmed'?'confirmed':''}">${task.type_source==='confirmed'?'Type confirmed':'Suggested type'}</span></div><div class="file-links" hidden></div>
    ${extra.length?`<div class="related-types">Also uses: ${extra.map(key=>`<a href="#type=${esc(key)}">${esc(typeById(key)?.label||key)}</a>`).join('')}</div>`:''}
    <p class="task-note" ${task.notes?'':'hidden'}>${esc(task.notes)}</p><details class="task-edit"><summary>Notes & task-type assignment</summary><div class="task-edit-content"></div></details></div></article>`;
}
async function renderPractice(ticket) {
  const type=typeById(state.type);
  if(!type){$('#task-cards').innerHTML='<div class="empty-types">This task type does not exist. <a href="#">Browse all types</a>.</div>';return;}
  const topic=topicById(type.topic);
  $('#type-heading').innerHTML=`<div class="type-path">${esc(topic?.area||'Review')} / ${esc(topic?.label||'Task types')}</div><h1 id="practice-title">${esc(type.label)}</h1>`;
  $('#approach-status').innerHTML=options(type.status);
  $('#approach-status').className='status-select '+type.status;
  $('#approach-notes').value=type.notes;
  $('#approach-text').textContent=type.approach;
  $('#approach-hint').open=false;
  $('#task-cards').setAttribute('aria-busy','true');
  $('#task-cards').innerHTML='<p class="muted">Loading similar questions…</p>';
  $('#question-count').textContent='Loading similar questions…';
  $('#task-pages').innerHTML='';
  const params=new URLSearchParams({...filters(),type:state.type,group:'type',page_size:'8',page:state.page||'1',status:state.status||'',q:state.q||''});
  const result=await api('/api/tasks?'+params);
  if(ticket!==requestId)return;
  taskResult=result;
  const layout=state.view|| (state.format==='structured'?'list':'compare');
  $('#task-cards').className=layout==='compare'?'compare':'';
  document.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===layout)));
  $('#question-count').textContent=`${number(result.total)} similar questions${state.format==='1'?' · multiple choice':''} · ${number(type.solved)} solved`;
  $('#task-cards').innerHTML=result.tasks.map(taskCard).join('')||'<div class="empty-types">No questions match these filters.<br><button class="text-button" data-reset-question>Show all questions in this type</button></div>';
  $('#task-cards').setAttribute('aria-busy','false');
  const pages=Math.max(1,Math.ceil(result.total/result.page_size));
  $('#task-pages').innerHTML=pages>1?`<button data-page="${result.page-1}" ${result.page===1?'disabled':''}>← Previous</button><span>Page ${result.page} of ${number(pages)}</span><button data-page="${result.page+1}" ${result.page===pages?'disabled':''}>Next →</button>`:'';
}
async function render() {
  const ticket=++requestId;
  const isType=Boolean(state.type);
  const toolbar=$('.browse-toolbar');
  if(isType){
    if(toolbar.parentElement!==$('#practice-filters')){
      $('#practice-filters').append(toolbar);
      $('#practice-filters').open=Boolean(state.q);
    }
  }else if(toolbar.parentElement!==$('#practice')){
    $('#practice').insertBefore(toolbar,$('#type-overview'));
  }
  $('#overview-intro').hidden=isType;$('#type-overview').hidden=isType;$('#type-practice').hidden=!isType;
  $('#search').value=state.q||'';
  $('#search').placeholder=isType?'Search these questions or your notes…':'Find a task type, e.g. base quantity or potential divider';
  $('#search').setAttribute('aria-label',isType?'Search these questions and notes':'Search task types');
  $('#topic').closest('label').hidden=isType;
  $('#format').value=state.format||'';
  $('#type-status').value=state.type_status||'';$('#question-status').value=state.status||'';
  try {
    const data=await api('/api/task-types?'+new URLSearchParams(filters()));
    if(ticket!==requestId)return;
    catalogue=data;renderNav();
    const actual=catalogue.types.filter(type=>type.total && type.id!=='unassigned');
    const known=actual.filter(type=>['know_how','solved'].includes(type.status)).length;
    $('#bank-summary').innerHTML=`<span><strong>${actual.length}</strong>task types</span><span><strong>${number(data.assigned)}</strong>grouped questions</span><span><strong>${known}</strong>approaches understood</span>`;
    document.title=(isType?(typeById(state.type)?.label||'Task type'):'Physics task types')+' · Paperwork';
    if(isType)await renderPractice(ticket);else renderOverview();
  }catch(error){
    if(ticket!==requestId)return;
    const target=isType?$('#task-cards'):$('#type-cards');
    target.innerHTML=`<div class="empty-types">${esc(error.message)}<br><button class="text-button" data-retry>Retry</button></div>`;
    target.setAttribute('aria-busy','false');toast(error.message,true);
  }
}
async function save(body) {
  $('#save-state').textContent='Saving…';
  try{const result=await api('/api/marks',body);$('#save-state').textContent='✓ Saved on this laptop';return result;}
  catch(error){$('#save-state').textContent='Save failed — please retry';throw error;}
}
function editContents(task) {
  return `<label>Your notes<textarea class="question-notes" maxlength="20000" rows="3" placeholder="My approach, mistakes, or what to revisit…">${esc(task.notes)}</textarea></label><label>Task types for this numbered question</label><p class="muted">Select the specific approaches it uses. Confirm the current choices or correct them. An empty selection puts the question in the unassigned queue.</p><input class="type-option-filter" type="search" aria-label="Find a task type for this question" placeholder="Filter task types…"><fieldset class="type-options" aria-label="Task types">${catalogue.types.filter(type=>type.id!=='unassigned').map(type=>`<label class="type-option"><input type="checkbox" value="${type.id}" ${task.task_types.includes(type.id)?'checked':''}><span>${esc(type.label)}</span></label>`).join('')}</fieldset><div class="edit-actions"><button class="primary-button" data-save-question>Save notes & confirm types</button><button class="text-button" data-reset-types>Reset to suggested types</button></div>`;
}
document.addEventListener('toggle',event=>{
  if(!event.target.matches('.task-edit') || !event.target.open)return;
  const card=event.target.closest('.task-card');
  const container=card.querySelector('.task-edit-content');
  if(!container.innerHTML)container.innerHTML=editContents(taskResult.tasks.find(task=>task.id===card.dataset.id));
},true);
document.addEventListener('error',event=>{if(event.target.matches('img'))event.target.parentElement.classList.add('broken');},true);
document.addEventListener('input',event=>{
  if(event.target.matches('.type-option-filter')){
    const term=event.target.value.toLowerCase();
    event.target.closest('.task-edit').querySelectorAll('.type-option').forEach(label=>label.hidden=!label.textContent.toLowerCase().includes(term));
  }
});
document.addEventListener('change',async event=>{
  if(!event.target.matches('[data-question-status]'))return;
  const select=event.target,card=select.closest('.task-card'),task=taskResult.tasks.find(task=>task.id===card.dataset.id);
  const previous=task.status,currentType=typeById(state.type),ticket=requestId;select.disabled=true;
  try{
    await save({updates:[{kind:'task',id:task.id,status:select.value}]});
    task.status=select.value;select.className='status-select '+task.status;
    currentType[previous]-=1;currentType[task.status]+=1;
    if(ticket===requestId)$('#question-count').textContent=`${number(taskResult.total)} similar questions · ${number(currentType.solved)} solved`;
    toast('Question progress saved');
    if(ticket===requestId && state.status)await render();
  }catch(error){select.value=previous;toast(error.message,true);}
  finally{select.disabled=false;}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');
  if(!button)return;
  if(button.dataset.view){navigate({view:button.dataset.view});return;}
  if(button.matches('[data-reset]')){navigate({topic:'',q:'',type_status:'',format:'',page:''});return;}
  if(button.matches('[data-reset-question]')){navigate({q:'',status:'',format:'',page:''});return;}
  if(button.matches('[data-retry]')){render();return;}
  if(button.dataset.page){navigate({page:button.dataset.page});$('#type-practice').scrollIntoView({block:'start'});return;}
  const card=button.closest('.task-card');if(!card)return;
  const task=taskResult.tasks.find(task=>task.id===card.dataset.id);if(!task)return;
  if(button.hasAttribute('data-zoom')){
    $('#zoom-title').textContent='Question '+task.number+' · original crop';
    $('#zoom-content').innerHTML=task.images.map(region=>`<img src="${esc(region.url)}" alt="Original question ${task.number}, page ${region.page}">`).join('');
    $('#zoom').showModal();return;
  }
  button.disabled=true;
  try {
    if(button.hasAttribute('data-files')){
      const container=card.querySelector('.file-links');
      if(container.innerHTML){container.hidden=!container.hidden;return;}
      const detail=await api('/api/tasks/'+task.id);
      container.innerHTML=detail.files.map(file=>`<a href="${esc(file.url)}" target="_blank" rel="noopener">${esc(file.label)} ↗${file.available?'':' (remote)'}</a>`).join('');container.hidden=false;
    }else if(button.hasAttribute('data-save-question')){
      const types=[...card.querySelectorAll('.type-options input:checked')].map(input=>input.value);
      const notes=card.querySelector('.question-notes').value;
      await save({updates:[{kind:'task',id:task.id,notes}],types:{[task.id]:types}});
      task.notes=notes;task.task_types=types;task.type_source='confirmed';
      const preview=card.querySelector('.task-note');preview.textContent=notes;preview.hidden=!notes;
      card.querySelector('.assignment-tag').textContent='Type confirmed';card.querySelector('.assignment-tag').classList.add('confirmed');
      toast('Notes and task types saved');
      if((state.type==='unassigned' && types.length) || (state.type!=='unassigned' && !types.includes(state.type)))await render();
    }else if(button.hasAttribute('data-reset-types')){
      await save({updates:[],types:{[task.id]:null}});toast('Automatic task types restored');await render();
    }
  }catch(error){toast(error.message,true);}
  finally{button.disabled=false;}
});
$('#approach-status').addEventListener('change',async event=>{
  const select=event.target,type=typeById(state.type),previous=type.status;select.disabled=true;
  try{await save({updates:[{kind:'group',id:'tasks:type:'+type.id,status:select.value}]});type.status=select.value;select.className='status-select '+select.value;toast('Your grasp of this approach is saved');}
  catch(error){select.value=previous;toast(error.message,true);}
  finally{select.disabled=false;}
});
$('#save-approach').addEventListener('click',async()=>{
  const button=$('#save-approach'),type=typeById(state.type),notes=$('#approach-notes').value;button.disabled=true;
  try{await save({updates:[{kind:'group',id:'tasks:type:'+type.id,notes}]});type.notes=notes;toast('Approach notes saved');}
  catch(error){toast(error.message,true);}finally{button.disabled=false;}
});
$('#search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>navigate({q:$('#search').value,page:''},true),300);});
$('#topic').addEventListener('change',()=>navigate({topic:$('#topic').value,page:''}));
$('#format').addEventListener('change',()=>navigate({format:$('#format').value,page:''}));
$('#type-status').addEventListener('change',()=>navigate({type_status:$('#type-status').value,page:''}));
$('#question-status').addEventListener('change',()=>navigate({status:$('#question-status').value,page:''}));
$('#close-zoom').addEventListener('click',()=>$('#zoom').close());
$('#restore').addEventListener('click',()=>$('#restore-file').click());
$('#restore-file').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  $('#restore').disabled=true;
  try{if(file.size>20_000_000)throw new Error('Choose a progress backup under 20 MB.');await api('/api/import',JSON.parse(await file.text()));toast('Progress and type corrections restored');await render();}
  catch(error){toast(error.message,true);}finally{$('#restore').disabled=false;event.target.value='';}
});
window.addEventListener('hashchange',()=>{clearTimeout(searchTimer);state=query();render();window.scrollTo({top:0});});
state=query();render();
