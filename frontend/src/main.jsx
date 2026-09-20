import TradeJournal from './TradeJournal.jsx';
import DatePicker from './components/DatePicker.jsx';
import Select from './components/Select.jsx';
import React, {useEffect, useState, useRef} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import './material.css';
import Calendar from './Calendar.jsx';
import Attachments from './Attachments.jsx';
const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
const emptyTrade = () => ({symbol:'',side:'Long',pnl:'',notes:''});
const blank = (date, rules) => ({date, plan:'', reflection:'', draft_trade:emptyTrade(), trades:[], checks:rules.map(r=>({...r,status:'pending'}))});
function score(checks){
  const relevant=checks.filter(c=>c.status!=='na');
  if(!relevant.length || relevant.some(c=>c.status==='pending')) return {value:null,letter:'—'};
  const value=Math.round(100*relevant.filter(c=>c.status==='followed').reduce((n,c)=>n+c.weight,0)/relevant.reduce((n,c)=>n+c.weight,0));
  return {value,letter:value>=90?'A':value>=80?'B':value>=70?'C':value>=60?'D':'F'};
}
const money = n => new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n);
function NavIcon({index}) {
 const shapes=[<><rect x="4" y="3" width="16" height="18" rx="3"/><path d="m8 12 2 2 5-5M8 18h8"/></>,<><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18M8 14h1m6 0h1m-8 4h1m6 0h1"/></>,<><path d="M5 4h14v17l-7-3-7 3zM9 8h6m-6 4h6"/></>,<><path d="M3 11a9 9 0 1 1 2 7M3 5v6h6m3-5v6l4 2"/></>];
 return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{shapes[index]}</svg>;
}
function App(){
 const [theme,setTheme]=useState(()=>{try{return localStorage.getItem('followthrough-theme')==='dark'?'dark':'light'}catch{return 'light'}});
 useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('followthrough-theme',theme)}catch{}},[theme]);
 const [data,setData]=useState(null),[day,setDay]=useState(null),[tab,setTab]=useState('Daily review'),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 const [rule,setRule]=useState({text:'',weight:1}),[trade,setTrade]=useState({symbol:'',side:'Long',pnl:'',notes:''});
 const current=useRef(null), revision=useRef(0), savedRevision=useRef(0), pending=useRef(null), saveLatest=useRef(null);
 const [noticeId,setNoticeId]=useState(0);
 const notify=text=>{setMessage(text);setNoticeId(n=>n+1)};
 const load=()=>fetch('/api/state/').then(r=>{if(!r.ok)throw Error('Could not load your journal.');return r.json()}).then(d=>{setData(d);const initial=d.days.find(x=>x.date===today)||blank(today,d.rules);current.current=initial;setDay(initial);setTrade({...emptyTrade(),...initial.draft_trade});setError('')}).catch(e=>setError(`${e.message} Check that Django is running on port 8000.`));
 useEffect(()=>{load()},[]);
 useEffect(()=>{const warn=e=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[dirty]);
 const change=patch=>{current.current={...current.current,...patch};revision.current++;setDay(current.current);setDirty(true)};
 const changeTrade=value=>{setTrade(value);change({draft_trade:value})};
 const selectDate=async date=>{
   if(!date||date===current.current.date){setTab('Daily review');return}
   if(pending.current && !await pending.current)return;
   while(revision.current!==savedRevision.current){if(!await save('auto'))return}
   const next=data.days.find(d=>d.date===date)||blank(date,data.rules);
   current.current=next;revision.current=0;savedRevision.current=0;setDay(next);setDirty(false);setError('');setTrade({...emptyTrade(),...next.draft_trade});setTab('Daily review');
 };
 async function request(url,method,body){const res=await fetch(url,{method,headers:{'Content-Type':'application/json','X-CSRFToken':data.csrfToken},body:JSON.stringify(body)});const result=await res.json();if(!res.ok)throw Error(result.error||'Unable to save. Please try again.');return result;}
 async function save(kind='manual'){
   if(pending.current){const ok=await pending.current;if(kind==='manual'&&ok&&revision.current!==savedRevision.current)return save(kind);return ok;}
   if(!current.current || (kind==='auto' && revision.current===savedRevision.current))return true;
   const snapshot=structuredClone(current.current), version=revision.current;
   setBusy(true);setError('');
   const operation=(async()=>{try{
     const result=await request(`/api/days/${snapshot.date}/`,'PUT',snapshot);
     setData(d=>({...d,days:[result,...d.days.filter(x=>x.date!==result.date)].sort((a,b)=>b.date.localeCompare(a.date))}));
     if(current.current.date===snapshot.date){savedRevision.current=version;setDirty(revision.current!==version)}
     notify(`${kind==='auto'?'All set — autosaved':'Saved'} your journal for ${snapshot.date}.`);
     return true;
   }catch(e){setError(`Your changes are still here, but saving failed. ${e.message}`);return false}
   finally{pending.current=null;setBusy(false)}})();
   pending.current=operation;return operation;
 }
 saveLatest.current=save;
 useEffect(()=>{if(!dirty||busy)return;const timer=setTimeout(()=>saveLatest.current('auto'),3000);return()=>clearTimeout(timer)},[day,dirty,busy]);
 useEffect(()=>{const timer=setInterval(()=>saveLatest.current('auto'),30000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{if(!message)return;const timer=setTimeout(()=>setMessage(''),5000);return()=>clearTimeout(timer)},[message,noticeId]);
 async function saveRule(e){e.preventDefault();setBusy(true);setError('');try{const result=await request('/api/rules/','POST',rule);const rules=[...data.rules.filter(r=>r.id!==rule.id),result];setData(d=>({...d,rules}));if(!data.days.some(d=>d.date===day.date))change({checks:rules.map(r=>({...r,status:current.current.checks.find(c=>c.id===r.id)?.status||'pending'}))});setRule({text:'',weight:1});setMessage('Rule saved. Saved days keep their original rulebook.')}catch(e){setError(e.message)}finally{setBusy(false)}}
 function addTrade(e){e.preventDefault();change({trades:[...day.trades,{...trade,symbol:trade.symbol.trim().toUpperCase()}],draft_trade:emptyTrade()});setTrade(emptyTrade())}
 if(!data||!day)return <main className="loading"><h1>Followthrough</h1><p role="status">{error||'Opening your journal…'}</p>{error&&<button onClick={load}>Try again</button>}</main>;
 const grade=score(day.checks),pnl=day.trades.reduce((sum,t)=>sum+Number(t.pnl),0),completed=day.checks.filter(c=>c.status!=='pending').length;
 return <div className="shell"><aside><a className="brand" href="#" onClick={e=>{e.preventDefault();setTab('Daily review')}}><span className="mark">✓</span>Followthrough</a><span className="eyebrow workspace">PERSONAL WORKSPACE</span><nav>{['Daily review','Calendar','Rulebook'].map((label,i)=><button className={tab===label?'active':''} key={label} onClick={()=>{setTab(label);setMessage('');setError('')}}><span aria-hidden="true"><NavIcon index={i}/></span>{label}</button>)}</nav><button className="theme-toggle" aria-pressed={theme==='dark'} onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?'☾ Dark mode':'☀ Light mode'}</button><div className="sidebar-note"><span className="eyebrow">THE GOAL</span><p>A repeatable process.<br/>One session at a time.</p><small>Local journal · SQLite</small></div></aside>
 <main><header><div><p className="eyebrow">TRADING / {tab.toUpperCase()}</p><h1>{tab==='Daily review'?'Grade the process.':tab==='Calendar'?'Your execution, day by day.':tab==='Rulebook'?'Your rules. Your standard.':'Every session tells a story.'}</h1></div>{tab==='Daily review'&&<div className="header-actions"><span className={`reviewed-pill ${day.checks.length>0&&completed===day.checks.length?'is-reviewed':''}`} role="status" title="Reviewed when every rule has an assessment, including Not applicable."><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>{day.checks.length>0&&completed===day.checks.length?'Reviewed':'Not reviewed'}</span><DatePicker value={day.date} onChange={selectDate} disabled={busy}/><button className="primary" disabled={busy} onClick={()=>save('manual')}>{busy?'Saving…':'Save'}</button></div>}</header>
 {error&&<div className="alert error" role="alert">{error}</div>}{message&&<div key={noticeId} className="alert save-notice" role="status"><span aria-hidden="true">✓</span> {message}</div>}
 {tab==='Daily review'&&<><section className="stats"><div className="grade-stat"><span className="eyebrow">EXECUTION GRADE</span><div className="grade-number">{grade.letter}<span>{grade.value===null?'Awaiting review':`${grade.value}% adherence`}</span></div><p>{grade.value===null?'Assess each rule to calculate your grade.':'Your discipline score, independent of P&L.'}</p></div><div><span className="eyebrow">RULES REVIEWED</span><div className="stat-number">{completed}<span> / {day.checks.length}</span></div><div className="track"><div style={{width:`${day.checks.length?completed/day.checks.length*100:0}%`}}/></div></div><div><span className="eyebrow">NET P&L</span><div className={`stat-number ${pnl<0?'negative':''}`}>{pnl>0?'+':''}{money(pnl)}</div><p>{day.trades.length} trades · Account currency</p></div></section>
 <div className="columns"><div><section className="panel"><div className="panel-heading"><h2><span className="step">01</span> Session plan</h2><span className="subtle">Before the open</span></div><label htmlFor="plan">What does a well-executed session look like?</label><textarea id="plan" rows="4" maxLength="20000" placeholder="Setups to watch, entry criteria, risk limits, and when to sit out…" value={day.plan} onChange={e=>change({plan:e.target.value})}/></section>
 <section className="panel"><div className="panel-heading"><h2><span className="step">02</span> Rule adherence</h2><span className="subtle">Weighted review</span></div>{!day.checks.length?<div className="empty"><h3>Start with your trading rules</h3><p>Add your rules and their importance to create a daily checklist.</p><button onClick={()=>setTab('Rulebook')}>Build your rulebook →</button></div>:day.checks.map((c,i)=><div className="rule-row" key={c.id}><div className="rule-title"><span className="rule-index">{String(i+1).padStart(2,'0')}</span><div><strong>{c.text}</strong><small>Weight {c.weight}</small></div></div><label className="sr-only" htmlFor={`rule-${c.id}`}>Assessment: {c.text}</label><Select id={`rule-${c.id}`} className={`status-${c.status}`} value={c.status} onChange={e=>change({checks:day.checks.map(x=>x.id===c.id?{...x,status:e.target.value}:x)})}><option value="pending">Not reviewed</option><option value="followed">Followed</option><option value="broken">Broken</option><option value="na">Not applicable</option></Select></div>)}<p className="footnote">For “Every trade” rules, choose Followed only if every trade met the rule. Not applicable rules are excluded; unreviewed rules keep your grade pending.</p></section>
 <TradeJournal key={day.date} day={day} trade={trade} changeTrade={changeTrade} addTrade={addTrade} change={change}/></div>
 <div><section className="panel reflection"><div className="panel-heading"><h2><span className="step">04</span> Daily reflection</h2></div><label htmlFor="reflection">What will you repeat or change?</label><textarea id="reflection" rows="9" maxLength="20000" placeholder="Where did you follow the plan? What pulled you away? One thing to improve tomorrow…" value={day.reflection} onChange={e=>change({reflection:e.target.value})}/><div className="reflection-note">A good trade follows your plan.<br/>The outcome is only part of the story.</div></section><Attachments key={day.date} date={day.date} csrfToken={data.csrfToken} notify={notify}/><section className="scoring"><span className="eyebrow">HOW YOUR GRADE WORKS</span><p>Followed rule weights ÷ applicable rule weights × 100.</p><div className="grade-key">{[['A','90–100'],['B','80–89'],['C','70–79'],['D','60–69'],['F','0–59']].map(([g,r])=><div key={g}><strong>{g}</strong><small>{r}</small></div>)}</div><small>P&L never changes your execution grade.</small></section></div></div></>}
 {tab==='Rulebook'&&<div className="columns"><section className="panel"><div className="panel-heading"><h2>Trading rules</h2><span className="subtle">{data.rules.length} active</span></div>{!data.rules.length&&<div className="empty"><h3>Your rulebook is ready to write</h3><p>Use your own trading rules. Higher weights give a rule more influence on the daily grade.</p></div>}{data.rules.map(r=><div className="rule-row" key={r.id}><div><strong>{r.text}</strong><small>Weight {r.weight}</small></div><button onClick={()=>setRule(r)}>Edit</button></div>)}</section><section className="panel"><h2>{rule.id?'Edit rule':'Add a rule'}</h2><form onSubmit={saveRule} className="rule-form"><label>Rule<textarea required maxLength="300" rows="4" value={rule.text} onChange={e=>setRule({...rule,text:e.target.value})} placeholder="Describe the behavior you want to follow…"/></label><label>Importance (1–10)<input type="number" min="1" max="10" required value={rule.weight} onChange={e=>setRule({...rule,weight:Number(e.target.value)})}/></label><button className="primary" disabled={busy}>Save rule</button>{rule.id&&<button type="button" onClick={()=>setRule({text:'',weight:1})}>Cancel edit</button>}</form><p className="footnote">Changes apply to unsaved days. Saved days retain their original rules and weights.</p></section></div>}
 {tab==='Calendar'&&<Calendar days={data.days} today={today} onOpen={selectDate}/>}

 <footer><span>FOLLOWTHROUGH / Personal trading journal</span><span>{dirty?'Unsaved changes': 'Make the process count.'}</span></footer></main></div>
}
createRoot(document.getElementById('root')).render(<App/>);
