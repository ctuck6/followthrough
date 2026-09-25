import AccountScope, {AccountSwitcher, useAccount} from './AccountScope.jsx';
import Statistics from './Statistics.jsx';
import PerformanceCards from './PerformanceCards.jsx';
import {ruleFollowing} from './performance.js';
import Rulebook from './Rulebook.jsx';
import Settings from './Settings.jsx';
import Strategies from './Strategies.jsx';
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
 const shapes=[<><rect x="4" y="3" width="16" height="18" rx="3"/><path d="m8 12 2 2 5-5M8 18h8"/></>,<><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18M8 14h1m6 0h1m-8 4h1m6 0h1"/></>,<><path d="M5 4h14v17l-7-3-7 3zM9 8h6m-6 4h6"/></>,<><path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2Z"/></>,<><path d="M3 21h18"/><rect x="4" y="12" width="3" height="6" rx="1"/><rect x="10" y="7" width="3" height="11" rx="1"/><rect x="16" y="3" width="3" height="15" rx="1"/></>,<><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>];
 return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{shapes[index]}</svg>;
}
function App(){
 const {accountId}=useAccount();
 const [tab,setTab]=useState('Daily review'),[selectedDate,setSelectedDate]=useState(today);
 return <Workspace key={accountId} tab={tab} setTab={setTab} selectedDate={selectedDate} setSelectedDate={setSelectedDate}/>;
}
function Workspace({tab,setTab,selectedDate,setSelectedDate}){
 const {accountId,scopedFetch,beforeSwitch,refreshAccounts}=useAccount();
 const [theme,setTheme]=useState(()=>{try{return localStorage.getItem('followthrough-theme')==='dark'?'dark':'light'}catch{return 'light'}});
 useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('followthrough-theme',theme)}catch{}},[theme]);
 const [data,setData]=useState(null),[day,setDay]=useState(null),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 const [rule,setRule]=useState({text:'',weight:1}),[trade,setTrade]=useState({symbol:'',side:'Long',pnl:'',notes:''});
 const clearing=useRef(false);
 const current=useRef(null), revision=useRef(0), savedRevision=useRef(0), pending=useRef(null), saveLatest=useRef(null);
 const [noticeId,setNoticeId]=useState(0);
 const [ledger,setLedger]=useState({executions:[],summaries:{},open_lots:[]});
 useEffect(()=>{scopedFetch('/api/executions/').then(r=>{if(!r.ok)throw Error('Could not load executions.');return r.json()}).then(setLedger).catch(e=>setError(e.message))},[]);
 async function updatedLedger(result,dates){
  setLedger(result);
  if(pending.current&&!await pending.current)return;
  while(revision.current!==savedRevision.current){if(!await save('auto'))return}
  const response=await scopedFetch('/api/state/');if(!response.ok)throw Error('Executions saved. Reload to refresh session dates.');
  const fresh=await response.json();setData(fresh);
  const target=dates?.includes(current.current.date)?current.current.date:dates?.slice().sort().at(-1);
  if(target&&target!==current.current.date){setSelectedDate(target);const next=fresh.days.find(d=>d.date===target)||blank(target,fresh.rules);current.current=next;revision.current=0;savedRevision.current=0;setDay(next);setDirty(false);setTrade({...emptyTrade(),...next.draft_trade});setTab('Daily review')}
 }
 const notify=text=>{setMessage(text);setNoticeId(n=>n+1)};
 const load=()=>scopedFetch('/api/state/').then(r=>{if(!r.ok)throw Error('Could not load your journal.');return r.json()}).then(d=>{setData(d);const initial=d.days.find(x=>x.date===selectedDate)||blank(selectedDate,d.rules);current.current=initial;setDay(initial);setTrade({...emptyTrade(),...initial.draft_trade});setError('')}).catch(e=>setError(`${e.message} Check that Django is running on port 8000.`));
 useEffect(()=>{load()},[]);
 useEffect(()=>{const warn=e=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[dirty]);
 const change=patch=>{current.current={...current.current,...patch};revision.current++;setDay(current.current);setDirty(true)};
 const changeTrade=value=>{setTrade(value);change({draft_trade:value})};
 const selectDate=async date=>{
   if(!date||date===current.current.date){setTab('Daily review');return}
   if(pending.current && !await pending.current)return;
   while(revision.current!==savedRevision.current){if(!await save('auto'))return}
   setSelectedDate(date);
   const next=data.days.find(d=>d.date===date)||blank(date,data.rules);
   current.current=next;revision.current=0;savedRevision.current=0;setDay(next);setDirty(false);setError('');setTrade({...emptyTrade(),...next.draft_trade});setTab('Daily review');
 };
 async function request(url,method,body){const res=await scopedFetch(url,{method,headers:{'Content-Type':'application/json','X-CSRFToken':data.csrfToken},body:JSON.stringify(body)});const result=await res.json();if(!res.ok)throw Error(result.error||'Unable to save. Please try again.');return result;}
 async function save(kind='manual'){
   if(clearing.current)return false;
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
 async function accountDataAction(id,kind){
   if(pending.current&&!await pending.current)throw Error('Save your pending journal edits before continuing.');
   while(revision.current!==savedRevision.current){if(!await save('auto'))throw Error('Save your pending journal edits before continuing.')}
   clearing.current=true;setBusy(true);
   try{
     const deleting=kind==='delete';
     const result=await request(`/api/accounts/${id}/${deleting?'':'data/'}`,'DELETE',{confirmation:`${deleting?'DELETE':'CLEAR'}_ACCOUNT_${id}`});
     if(String(id)===accountId){
       const clean=blank(current.current.date,data.rules);
       current.current=clean;revision.current=0;savedRevision.current=0;
       setDay(clean);setTrade(emptyTrade());setDirty(false);setError('');
       setData(d=>({...d,days:[]}));setLedger({executions:[],trades:[],summaries:{},open_lots:[]});
     }
     try{Object.keys(localStorage).filter(key=>key.startsWith(`followthrough-manual-fill-${id}-`)).forEach(key=>localStorage.removeItem(key))}catch{}
     await refreshAccounts();
     return result;
   }finally{clearing.current=false;setBusy(false)}
 }
 beforeSwitch.current=async()=>{
   if(pending.current&&!await pending.current)return false;
   while(revision.current!==savedRevision.current){if(!await save('auto'))return false}
   return true;
 };
 saveLatest.current=save;
 useEffect(()=>{if(!dirty||busy)return;const timer=setTimeout(()=>saveLatest.current('auto'),3000);return()=>clearTimeout(timer)},[day,dirty,busy]);
 useEffect(()=>{const timer=setInterval(()=>saveLatest.current('auto'),30000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{if(!message)return;const timer=setTimeout(()=>setMessage(''),5000);return()=>clearTimeout(timer)},[message,noticeId]);
 async function saveRule(e){e.preventDefault();setBusy(true);setError('');try{const result=await request('/api/rules/','POST',rule);const rules=[...data.rules.filter(r=>r.id!==rule.id),result];setData(d=>({...d,rules}));if(!data.days.some(d=>d.date===day.date))change({checks:rules.map(r=>({...r,status:current.current.checks.find(c=>c.id===r.id)?.status||'pending'}))});setRule({text:'',weight:1});setMessage('Rule saved. Saved days keep their original rulebook.')}catch(e){setError(e.message)}finally{setBusy(false)}}
 function addTrade(e){e.preventDefault();change({trades:[...day.trades,{...trade,symbol:trade.symbol.trim().toUpperCase()}],draft_trade:emptyTrade()});setTrade(emptyTrade())}
 if(!data||!day)return <main className="loading"><h1>Followthrough</h1><p role="status">{error||'Opening your journal…'}</p>{error&&<button onClick={load}>Try again</button>}</main>;
 const following=ruleFollowing(day.checks);
 const grade=score(day.checks),pnl=day.trades.reduce((sum,t)=>sum+Number(t.pnl),0),completed=day.checks.filter(c=>c.status!=='pending').length;
 return <div className="shell"><aside><a className="brand" href="#" onClick={e=>{e.preventDefault();setTab('Daily review')}}><span className="mark">✓</span>Followthrough</a><span className="eyebrow workspace">PERSONAL WORKSPACE</span><nav>{['Daily review','Calendar','Rulebook','Strategies','Statistics','Settings'].map((label,i)=><button className={tab===label?'active':''} key={label} onClick={()=>{setTab(label);setMessage('');setError('')}}><span aria-hidden="true"><NavIcon index={i}/></span>{label}</button>)}</nav><button className="theme-toggle" aria-pressed={theme==='dark'} onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?'☾ Dark mode':'☀ Light mode'}</button><div className="sidebar-note"><span className="eyebrow">THE GOAL</span><p>A repeatable process.<br/>One session at a time.</p></div></aside>
 <main><header><div><p className="eyebrow">TRADING / {tab.toUpperCase()}</p><h1>{tab==='Daily review'?'Grade the process.':tab==='Calendar'?'Your execution, day by day.':tab==='Rulebook'?'Your rules. Your standard.':tab==='Strategies'?'Define your edge.':tab==='Statistics'?'Your performance, in perspective.':'Your settings.'}</h1></div>{tab==='Daily review'&&<div className="header-actions"><span className={`reviewed-pill ${day.checks.length>0&&completed===day.checks.length?'is-reviewed':''}`} role="status" title="Reviewed when every rule has an assessment, including Not applicable."><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>{day.checks.length>0&&completed===day.checks.length?'Reviewed':'Not reviewed'}</span><DatePicker value={day.date} onChange={selectDate} disabled={busy}/><AccountSwitcher/></div>}{['Calendar','Statistics'].includes(tab)&&<div id="page-controls"/>}{tab==='Strategies'&&<AccountSwitcher/>}</header>
 {error&&<div className="alert error" role="alert">{error}</div>}{message&&<div key={noticeId} className="alert save-notice" role="status"><span aria-hidden="true">✓</span> {message}</div>}
 {tab==='Daily review'&&<><section className="stats"><div className="grade-stat"><span className="eyebrow">EXECUTION GRADE</span><div className="grade-number">{grade.letter}<span>{grade.value===null?'Awaiting review':`${grade.value}% adherence`}</span></div><p>{grade.value===null?'Assess each rule to calculate your grade.':'Your discipline score, independent of P&L.'}</p></div><div><span className="eyebrow">RULES FOLLOWED</span><div className="stat-number">{following.followed}<span> / {following.total}</span></div><div className="track"><div style={{width:`${following.total?following.followed/following.total*100:0}%`}}/></div></div><div className="daily-pnl-card"><span className="eyebrow">REALIZED NET P&L</span>{Object.entries(ledger.summaries[day.date]||{}).map(([c,s])=><div key={c} className={`daily-pnl-value ${Number(s.net)<0?'is-loss':'is-gain'}`}><div className="stat-number"><span className="pnl-trend" aria-hidden="true">{Number(s.net)<0?'↘':'↗'}</span>{Number(s.net)>0?'+':''}{money(s.net)} <small>{c}</small></div>{s.incomplete>0&&<p>Incomplete — missing cost basis</p>}</div>)}{!ledger.summaries[day.date]&&<p>No executions yet</p>}{day.trades.length>0&&<p>Legacy entries: {money(pnl)} · Account currency</p>}</div></section>
 <PerformanceCards trades={ledger.trades} summaries={ledger.summaries} start={day.date}/>
 <div className="columns"><div><section className="panel"><div className="panel-heading"><h2><span className="step">01</span> Session plan</h2><span className="subtle">Before the open</span></div><label htmlFor="plan">What does a well-executed session look like?</label><textarea id="plan" rows="4" maxLength="20000" placeholder="Setups to watch, entry criteria, risk limits, and when to sit out…" value={day.plan} onChange={e=>change({plan:e.target.value})}/></section>
 <section className="panel"><div className="panel-heading"><h2><span className="step">02</span> Rule adherence</h2><span className="subtle">Weighted review</span></div>{!day.checks.length?<div className="empty"><h3>Start with your trading rules</h3><p>Add your rules and their importance to create a daily checklist.</p><button onClick={()=>setTab('Rulebook')}>Build your rulebook →</button></div>:day.checks.map((c,i)=><div className="rule-row" key={c.id}><div className="rule-title"><span className="rule-index">{String(i+1).padStart(2,'0')}</span><div><strong>{c.text}</strong><small>Weight {c.weight}</small></div></div><label className="sr-only" htmlFor={`rule-${c.id}`}>Assessment: {c.text}</label><Select id={`rule-${c.id}`} className={`status-${c.status}`} value={c.status} onChange={e=>change({checks:day.checks.map(x=>x.id===c.id?{...x,status:e.target.value}:x)})}><option value="pending">Not reviewed</option><option value="followed">Followed</option><option value="broken">Broken</option><option value="na">Not applicable</option></Select></div>)}<p className="footnote">For “Every trade” rules, choose Followed only if every trade met the rule. Not applicable rules are excluded; unreviewed rules keep your grade pending.</p></section>
 <TradeJournal key={day.date} day={day} change={change} ledger={ledger} request={request} onUpdated={updatedLedger} notify={notify} csrfToken={data.csrfToken}/></div>
 <div><section className="panel reflection"><div className="panel-heading"><h2><span className="step">04</span> Daily reflection</h2></div><label htmlFor="reflection">What will you repeat or change?</label><textarea id="reflection" rows="9" maxLength="20000" placeholder="Where did you follow the plan? What pulled you away? One thing to improve tomorrow…" value={day.reflection} onChange={e=>change({reflection:e.target.value})}/><div className="reflection-note">A good trade follows your plan.<br/>The outcome is only part of the story.</div></section><Attachments key={day.date} date={day.date} csrfToken={data.csrfToken} notify={notify}/><section className="scoring"><span className="eyebrow">HOW YOUR GRADE WORKS</span><p>Followed rule weights ÷ applicable rule weights × 100.</p><div className="grade-key">{[['A','90–100'],['B','80–89'],['C','70–79'],['D','60–69'],['F','0–59']].map(([g,r])=><div key={g}><strong>{g}</strong><small>{r}</small></div>)}</div><small>P&L never changes your execution grade.</small></section></div></div></>}
 {tab==='Rulebook'&&<Rulebook rules={data.rules} request={request} notify={notify} onUpdated={rules=>{setData(d=>({...d,rules}));if(!data.days.some(d=>d.date===current.current.date))change({checks:rules.map(r=>({...r,status:current.current.checks.find(c=>c.id===r.id)?.status||'pending'}))})}}/>}
 {tab==='Strategies'&&<Strategies request={request} notify={notify}/>}
 {tab==='Statistics'&&<Statistics today={today}/>}
 {tab==='Settings'&&<Settings request={request} notify={notify} onAccountDataAction={accountDataAction}/>}
 {tab==='Calendar'&&<Calendar trades={ledger.trades} days={data.days} summaries={ledger.summaries} today={today} onOpen={selectDate}/>}

 <footer><span>FOLLOWTHROUGH / Personal trading journal</span><span>{dirty?'Unsaved changes': 'Make the process count.'}</span></footer></main></div>
}
createRoot(document.getElementById('root')).render(<AccountScope><App/></AccountScope>);
