'use strict';
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statuses={unmarked:'Not marked',to_process:'To process',know_how:'Know how to solve',solved:'Solved'};
const initial=new URLSearchParams(location.hash.slice(1));
const filters=Object.fromEntries(['collection','topic','paper','year','session','status','q','review','document'].map(key=>[key,initial.get(key)||'']));
filters.group=initial.get('group')||'topic';
filters.page=Number(initial.get('page'))||1;
let data, selected=new Set(), activeGroups=new Map(), target=null, task=null, topicsChanged=false, resetTopics=false;
let busy=false, requestSerial=0, searchTimer, toastTimer;
const topicLabel=id=>data?.topics.find(topic=>topic.id===id)?.label||id;

async function api(url,options){
  const response=await fetch(url,options);
  let result;try{result=await response.json();}catch{throw new Error('The backend returned an unreadable response.');}
  if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);
  return result;
}
function toast(message,error=false){
  clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').classList.toggle('error',error);
  $('#toast').setAttribute('role',error?'alert':'status');$('#toast').hidden=false;
  toastTimer=setTimeout(()=>$('#toast').hidden=true,error?8000:3500);
}
function options(value,placeholder=''){
  return(placeholder?`<option value="">${esc(placeholder)}</option>`:'')+Object.entries(statuses).map(([id,label])=>`<option value="${id}" ${id===value?'selected':''}>${label}</option>`).join('');
}
function progressSelect(kind,id,status,label){
  return`<select class="status-select ${status}" data-mark="${kind}" data-id="${esc(id)}" aria-label="${esc(label)}">${options(status)}</select>`;
}
function query(){return new URLSearchParams(Object.entries(filters).filter(([,value])=>value!==''&&value!==null));}
function updateHash(){const params=query();if(filters.page===1)params.delete('page');if(filters.group==='topic')params.delete('group');history.replaceState(null,'',location.pathname+(params.size?'#'+params:''));}

async function load(scroll=false){
  const serial=++requestSerial;$('#questions').setAttribute('aria-busy','true');
  try{
    const result=await api('/api/tasks?'+query());
    if(serial!==requestSerial)return;
    data=result;filters.page=data.page;render();updateHash();
    if(scroll)$('#questions-section').scrollIntoView({block:'start'});
    return true;
  }catch(error){
    if(serial!==requestSerial)return;
    $('#questions').innerHTML=`<div class="empty"><h3>Could not open the question bank.</h3><p>${esc(error.message)}</p><p>Build or update the index with <code>python3 -m past_papers.index_tasks</code>.</p><button class="quiet-button" data-retry>Try again</button></div>`;
    $('#result-count').textContent='Question index unavailable';return false;
  }finally{if(serial===requestSerial)$('#questions').setAttribute('aria-busy','false');}
}
function setFilters(changes,scroll=false){Object.assign(filters,changes);if(!Object.hasOwn(changes,'page'))filters.page=1;selected.clear();load(scroll);}
function reset(){setFilters({collection:'',topic:'',paper:'',year:'',session:'',status:'',q:'',review:'',document:'',group:'topic',page:1});}

function renderNavigation(){
  const total=Object.values(data.stats).reduce((a,b)=>a+b,0);
  $('#collections').innerHTML=[['','All questions',total],['yearly','Exam questions',data.collection_counts.yearly||0],['topical','Topical questions',data.collection_counts.topical||0]].map(([id,label,count])=>`<button class="nav-button ${filters.collection===id?'active':''}" data-collection="${id}" ${filters.collection===id?'aria-current="page"':''}><span class="nav-symbol" aria-hidden="true">${id==='topical'?'◈':'▤'}</span>${label}<span class="count">${count.toLocaleString()}</span></button>`).join('');
  const topicScroll=$('#topic-nav').scrollTop;
  const opened=new Map([...document.querySelectorAll('#topic-nav .topic-area')].map(node=>[node.querySelector('summary').textContent,node.open]));
  const areas=new Map();for(const topic of data.topics){if(!areas.has(topic.area))areas.set(topic.area,[]);areas.get(topic.area).push(topic);}
  $('#topic-nav').innerHTML=[...areas].map(([area,topics])=>`<details class="topic-area" ${opened.get(area)!==false?'open':''}><summary>${esc(area)}</summary>${topics.map(topic=>`<button class="nav-button ${filters.topic===topic.id?'active':''}" data-topic="${topic.id}" ${filters.topic===topic.id?'aria-current="page"':''}>${esc(topic.label)}<span class="count">${(data.topic_counts[topic.id]||0).toLocaleString()}</span></button>`).join('')}</details>`).join('');
  $('#topic-nav').scrollTop=topicScroll;
  const topicOptions='<option value="">All physics topics</option>'+[...areas].map(([area,topics])=>`<optgroup label="${esc(area)}">${topics.map(topic=>`<option value="${topic.id}">${esc(topic.label)}</option>`).join('')}</optgroup>`).join('');
  $('#topic-filter').innerHTML=topicOptions;$('#topic-filter').value=filters.topic;
  $('#year').innerHTML='<option value="">All years</option>'+data.years.map(year=>`<option>${year}</option>`).join('');
  for(const [selector,key] of [['#search','q'],['#year','year'],['#session','session'],['#paper-filter','paper'],['#group-by','group']])$(selector).value=filters[key];
  $('#review-only').checked=filters.review==='1';
}
function renderStats(){
  const count=Object.values(data.stats).reduce((a,b)=>a+b,0);
  $('#stats').innerHTML=`<div class="stat"><span class="stat-label">INDIVIDUAL QUESTIONS</span><strong class="stat-value">${count.toLocaleString()}</strong><span class="stat-foot">Across ${data.document_count} source documents</span></div>`+[
    ['solved','SOLVED','Questions you have completed'],['know_how','KNOW HOW TO SOLVE','Questions you understand'],['to_process','TO PROCESS','Your question practice queue']
  ].map(([id,label,foot])=>`<div class="stat"><span class="stat-label"><i class="status-dot ${id}"></i>${label}</span><strong class="stat-value">${(data.stats[id]||0).toLocaleString()}</strong><span class="stat-foot">${foot}</span></div>`).join('');
  $('#index-date').textContent='Question index updated '+new Date(data.indexed_at).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});
}
function questionMeta(item){
  const source=item.year?`9702/${item.filename.match(/_(\d{1,2})\.pdf$/)?.[1]||item.component||'?'} · ${data.sessions[item.session]||''} ${item.year}`:item.filename;
  return`${esc(source)}<span class="separator">·</span>Q${item.number}${item.occurrence>1?` (occurrence ${item.occurrence})`:''}<span class="separator">·</span>p. ${item.page}${item.end_page!==item.page?'–'+item.end_page:''}`;
}
function questionRow(item){
  return`<article class="question-row"><input type="checkbox" class="paper-check" data-select="${item.id}" aria-label="Select question ${item.number} from ${esc(item.filename)}" ${selected.has(item.id)?'checked':''}><div class="question-badge" aria-hidden="true">${item.number}<small>Q</small></div><div class="question-main"><button class="question-summary" data-open="${item.id}">${esc(item.summary||'Open question '+item.number)}</button><div class="question-meta">${questionMeta(item)}</div><div class="topic-tags">${item.topics.map(id=>`<button class="topic-chip" data-topic="${id}">${esc(topicLabel(id))}</button>`).join('')}<span class="topic-confidence ${item.topic_source==='confirmed'?'confirmed':''}">${item.topic_source==='confirmed'?'✓ Topic confirmed':item.confidence==='review'?'Review topic':'Suggested topics'}</span></div>${item.notes?`<span class="row-note-preview">${esc(item.notes)}</span>`:''}</div><div class="question-controls">${progressSelect('task',item.id,item.status,`Progress for question ${item.number} from ${item.filename}`)}<button class="open-question" data-open="${item.id}">Open question ↗</button></div></article>`;
}
function renderResults(){
  $('#questions-title').textContent=filters.topic?topicLabel(filters.topic):filters.paper?`Paper ${filters.paper} · ${data.papers[filters.paper]||'Questions'}`:filters.collection==='topical'?'Topical questions':filters.collection==='yearly'?'Exam questions':'All questions';
  $('#result-count').textContent=`${data.total.toLocaleString()} individual questions${filters.q||filters.status||filters.review?' match your filters':''}`;
  const tabTotal=Object.values(data.status_counts).reduce((a,b)=>a+b,0);
  $('#status-tabs').innerHTML=[['','All questions'],...Object.entries(statuses)].map(([id,label])=>`<button class="status-tab ${filters.status===id?'active':''}" data-status="${id}" aria-pressed="${filters.status===id}">${label}<span>${(id?data.status_counts[id]||0:tabTotal).toLocaleString()}</span></button>`).join('');
  activeGroups=new Map(data.groups.map(group=>[group.id,group]));
  const pageGroups=new Map();for(const item of data.tasks){if(!pageGroups.has(item.group_id))pageGroups.set(item.group_id,[]);pageGroups.get(item.group_id).push(item);}
  $('#questions').innerHTML=[...pageGroups].map(([key,items])=>{
    const group=activeGroups.get(key);
    return`<section class="paper-group" aria-label="${esc(group.label)}"><div class="group-heading"><div class="group-label"><h3>${esc(group.label)}</h3><span>${group.total.toLocaleString()} questions · ${group.solved} solved</span></div><div class="group-actions"><button class="group-note-button" data-group-notes="${esc(key)}">${group.notes?'▱ Notes':'＋ Notes'}</button><label><span>Group mark</span>${progressSelect('group',key,group.status,`Group mark for ${group.label}`)}</label><select class="group-bulk" data-group-bulk="${esc(key)}" aria-label="Mark all ${group.total} filtered questions in ${esc(group.label)}">${options('',`Mark all ${group.total} questions…`)}</select></div></div><div class="group-rows">${items.map(questionRow).join('')}</div></section>`;
  }).join('')||'<div class="empty"><span class="empty-symbol">◈</span><h3>No questions match.</h3><p>Try a different topic, year, or progress status.</p><button class="quiet-button" data-reset>Clear filters</button></div>';
  const pages=Math.max(1,Math.ceil(data.total/data.page_size));
  $('#pagination').innerHTML=`<button data-page="${data.page-1}" ${data.page===1?'disabled':''}>← Previous</button><span>Page ${data.page} of ${pages.toLocaleString()}</span><button data-page="${data.page+1}" ${data.page>=pages?'disabled':''}>Next →</button>`;
  $('#index-issues').hidden=!data.issues.length;
  $('#index-issues').textContent=`${data.issues.length} source documents to review`;
  renderSelection();
}
function renderSelection(){
  $('#bulk-bar').hidden=selected.size===0;$('#selection-count').textContent=`${selected.size} questions selected`;
  const picked=data?.tasks.filter(item=>selected.has(item.id)).length||0;
  $('#select-page').checked=!!data?.tasks.length&&picked===data.tasks.length;
  $('#select-page').indeterminate=picked>0&&picked<data.tasks.length;
}
function render(){renderNavigation();renderStats();renderResults();}
function setBusy(value){busy=value;$('#restore-button').disabled=value;$('#bulk-apply').disabled=value;$('#save-task').disabled=value;document.querySelectorAll('[data-mark],[data-group-bulk]').forEach(node=>node.disabled=value);}
async function save(payload,message='Question progress saved',endpoint='/api/marks'){
  if(busy){toast('Please wait for the current save to finish.');await load();return false;}
  setBusy(true);$('#save-state').textContent='Saving progress…';let saved=false;
  try{
    const result=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    selected.clear();await load();toast(result.updated_count?`${result.updated_count} questions updated`:message);saved=true;return true;
  }catch(error){toast(`Progress was not saved: ${error.message}`,true);await load();return false;}
  finally{setBusy(false);$('#save-state').innerHTML=saved?'<span class="small-dot"></span> Progress saved locally':'Save failed — please retry';}
}
function topicOptions(){return data.topics.map(topic=>`<option value="${topic.id}">${esc(topic.label)}</option>`).join('');}
function fillTopics(topics){
  $('#primary-topic').innerHTML=topicOptions();$('#primary-topic').value=topics[0];
  $('#extra-topics').innerHTML=data.topics.filter(topic=>topic.id!==topics[0]&&topic.id!=='unclassified').map(topic=>`<option value="${topic.id}" ${topics.slice(1).includes(topic.id)?'selected':''}>${esc(topic.label)}</option>`).join('');
  $('#extra-topics').disabled=topics[0]==='unclassified';
}
async function openQuestion(id){
  target={kind:'task',id};task=null;topicsChanged=false;resetTopics=false;
  const dialog=$('#task-dialog');dialog.classList.remove('group-editor');$('#task-reader').hidden=false;$('#topic-editor').hidden=false;
  $('#task-title').textContent='Opening question…';$('#task-source').textContent='';$('#task-files').innerHTML='';$('#task-images').innerHTML='<div class="empty"><span class="loading-ring"></span></div>';$('#task-text').textContent='';$('#task-notes').value='';$('#editor-message').textContent='';$('#save-task').disabled=true;
  $('#task-eyebrow').textContent='NUMBERED QUESTION';$('label[for="task-status"]').textContent='Question progress';
  dialog.showModal();
  try{
    const result=await api('/api/tasks/'+id);if(target?.id!==id||!dialog.open)return;task=result;
    $('#task-title').textContent=`Question ${task.number}${task.occurrence>1?` · occurrence ${task.occurrence}`:''}`;
    $('#task-source').textContent=task.filename+` · page ${task.page}${task.end_page!==task.page?'–'+task.end_page:''}`;
    $('#task-files').innerHTML=task.files.map(file=>`<a href="${esc(file.url)}" target="_blank" rel="noopener noreferrer">${esc(file.label)}${file.available?'':' (online)'} ↗</a>`).join('');
    $('#task-images').innerHTML=task.images.map((image,index)=>`<p class="question-image-label">Source page ${image.page}${task.images.length>1?` · part ${index+1} of ${task.images.length}`:''}</p><img class="question-image" src="${image.url}" loading="${index?'lazy':'eager'}" alt="Question ${task.number}, original PDF page ${image.page}">`).join('');
    $('#task-images').querySelectorAll('img').forEach(image=>image.addEventListener('error',()=>{const warning=document.createElement('p');warning.className='image-error';warning.textContent='Could not render this preview. Open the source question paper using the link above.';image.replaceWith(warning);}));
    $('#task-text').textContent=task.text;$('#task-status').innerHTML=options(task.status);$('#task-notes').value=task.notes;
    fillTopics(task.topics);$('#confirm-topics').checked=task.topic_source==='confirmed';
    $('#topic-hint').textContent=task.topic_source==='confirmed'?'Your confirmed categories.':'Suggested from this question’s content. You can adjust or confirm these topics.';
    $('#editor-message').textContent='Only this numbered question is marked. Its subparts stay together.';
    $('#save-task').disabled=false;$('.task-reader').scrollTop=0;$('.task-dialog-content').scrollTop=0;
  }catch(error){$('#task-images').innerHTML=`<p class="image-error">${esc(error.message)}</p>`;$('#task-title').textContent='Could not open question';}
}
function openGroup(key){
  const group=activeGroups.get(key);if(!group)return;
  target={kind:'group',id:key};task=null;$('#task-dialog').classList.add('group-editor');$('#task-reader').hidden=true;$('#topic-editor').hidden=true;
  $('#task-eyebrow').textContent='GROUP NOTES';$('#task-title').textContent=group.label;$('#task-source').textContent='A separate group mark. Individual question marks stay as they are.';
  $('label[for="task-status"]').textContent='Group mark';$('#task-status').innerHTML=options(group.status);$('#task-notes').value=group.notes;$('#editor-message').textContent='Use the group’s “Mark all … questions” menu to change individual marks.';$('#save-task').disabled=false;$('#task-dialog').showModal();
}

document.addEventListener('click',event=>{
  const collection=event.target.closest('[data-collection]');if(collection)setFilters({collection:collection.dataset.collection,document:''});
  const topic=event.target.closest('[data-topic]');if(topic)setFilters({topic:topic.dataset.topic,document:''});
  const status=event.target.closest('[data-status]');if(status)setFilters({status:status.dataset.status});
  const open=event.target.closest('[data-open]');if(open)openQuestion(open.dataset.open);
  const group=event.target.closest('[data-group-notes]');if(group)openGroup(group.dataset.groupNotes);
  const close=event.target.closest('[data-close]');if(close){close.closest('dialog').close();if(close.closest('#task-dialog'))target=null;}
  const page=event.target.closest('[data-page]');if(page&&!page.disabled){filters.page=Number(page.dataset.page);load(true);}
  if(event.target.closest('[data-reset]'))reset();
  if(event.target.closest('[data-retry]'))load();
  if(event.target.closest('[data-help]'))$('#help-dialog').showModal();
});
document.addEventListener('change',async event=>{
  const node=event.target;
  if(node.matches('[data-mark]'))await save({updates:[{kind:node.dataset.mark,id:node.dataset.id,status:node.value}]},node.dataset.mark==='group'?'Group mark saved':'Question progress saved');
  if(node.matches('[data-select]')){if(node.checked)selected.add(node.dataset.select);else selected.delete(node.dataset.select);renderSelection();}
  if(node.matches('[data-group-bulk]')&&node.value)await save({filters:{...filters},group_id:node.dataset.groupBulk,status:node.value},'', '/api/task-bulk');
});
$('#search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>setFilters({q:$('#search').value}),220);});
for(const [selector,key] of [['#topic-filter','topic'],['#paper-filter','paper'],['#year','year'],['#session','session'],['#group-by','group']])$(selector).addEventListener('change',()=>setFilters({[key]:$(selector).value}));
$('#review-only').addEventListener('change',()=>setFilters({review:$('#review-only').checked?'1':''}));
$('#reset-filters').addEventListener('click',reset);
$('#select-page').addEventListener('change',()=>{for(const item of data.tasks){if($('#select-page').checked)selected.add(item.id);else selected.delete(item.id);}renderResults();});
$('#clear-selection').addEventListener('click',()=>{selected.clear();renderResults();});
$('#bulk-apply').addEventListener('click',()=>save({updates:[...selected].map(id=>({kind:'task',id,status:$('#bulk-status').value}))},`${selected.size} questions updated`));
$('#primary-topic').addEventListener('change',()=>{const topics=[$('#primary-topic').value,...[...$('#extra-topics').selectedOptions].map(option=>option.value)].filter((value,index,all)=>all.indexOf(value)===index);fillTopics(topics[0]==='unclassified'?['unclassified']:topics);topicsChanged=true;resetTopics=false;$('#confirm-topics').checked=true;});
$('#extra-topics').addEventListener('change',()=>{topicsChanged=true;resetTopics=false;$('#confirm-topics').checked=true;});
$('#reset-topic').addEventListener('click',()=>{fillTopics(task.suggested_topics);topicsChanged=true;resetTopics=true;$('#confirm-topics').checked=false;$('#topic-hint').textContent='Automatic topics will be restored when you save.';});
$('#task-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!target)return;
  const payload={updates:[{...target,status:$('#task-status').value,notes:$('#task-notes').value}]};
  if(target.kind==='task'&&(topicsChanged||($('#confirm-topics').checked&&task.topic_source!=='confirmed'))){
    const primary=$('#primary-topic').value;const topics=primary==='unclassified'?['unclassified']:[primary,...[...$('#extra-topics').selectedOptions].map(option=>option.value)];
    payload.topics={[target.id]:resetTopics?null:topics};
  }
  if(await save(payload,target.kind==='group'?'Group progress saved':'Question progress saved')){$('#task-dialog').close();target=null;}
  else $('#editor-message').textContent='Could not save. Your text is still here; please retry.';
});
$('#index-issues').addEventListener('click',()=>{$('#issues-list').innerHTML=data.issues.map(issue=>`<div class="index-issue"><a href="/papers#q=${encodeURIComponent(issue.filename)}" target="_blank" rel="noopener noreferrer">${esc(issue.filename)} ↗</a><p>${esc(issue.note)}${issue.task_count?` · ${issue.task_count} questions extracted`:''}</p></div>`).join('');$('#issues-dialog').showModal();});
$('#restore-button').addEventListener('click',()=>$('#restore-file').click());
$('#restore-file').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  try{if(file.size>20_000_000)throw new Error('Backup exceeds 20 MB.');const payload=JSON.parse(await file.text());await save(payload,'Question and paper progress restored','/api/import');}
  catch(error){toast(`Could not restore: ${error.message}`,true);}finally{event.target.value='';}
});
load();
window.addEventListener('hashchange',()=>{
  const params=new URLSearchParams(location.hash.slice(1));
  for(const key of ['collection','topic','paper','year','session','status','q','review','document'])filters[key]=params.get(key)||'';
  filters.group=params.get('group')||'topic';filters.page=Number(params.get('page'))||1;
  selected.clear();if($('#task-dialog').open)$('#task-dialog').close();target=null;load();
});
setInterval(()=>{if(!document.hidden&&!busy&&!$('dialog[open]')&&!selected.size)load();},30000);
