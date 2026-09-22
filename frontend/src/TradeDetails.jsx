import React,{useEffect,useRef,useState} from 'react';
const TradeChart=React.lazy(()=>import('./TradeChart.jsx'));
import ExecutionList from './ExecutionList.jsx';
import Modal from './components/Modal.jsx';
import Attachments from './Attachments.jsx';
const money=(v,c)=>v===null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:c}).format(Number(v));
export default function TradeDetails({trade,executions=[],onUpdated,request,csrfToken,notify,onClose}){
 const [notes,setNotes]=useState(''),[ready,setReady]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState('Loading journal…');
 const [activeTab,setActiveTab]=useState('Chart');
 const tabs=['Chart','Executions','Notes'];
 const current=useRef(''),saved=useRef(''),pending=useRef(null);
 const url=`/api/trades/${trade.trade_id}/journal/`;
 useEffect(()=>{const controller=new AbortController();fetch(url,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('Could not load trade journal.');return r.json()}).then(d=>{current.current=saved.current=d.notes;setNotes(d.notes);setReady(true);setStatus('All changes saved')}).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return()=>controller.abort()},[url]);
 async function save(){
  if(pending.current){if(!await pending.current)return false;return save()}
  if(!ready||current.current===saved.current)return true;
  const snapshot=current.current;setSaving(true);setError('');setStatus('Saving…');
  const operation=(async()=>{try{await request(url,'PUT',{notes:snapshot});saved.current=snapshot;setStatus(current.current===snapshot?'All changes saved':'Unsaved changes');notify(`Saved journal for ${trade.symbol}.`);return true}catch(e){setError(e.message);setStatus('Could not save');return false}finally{pending.current=null;setSaving(false)}})();pending.current=operation;return operation;
 }
 useEffect(()=>{if(!ready||saving||notes===saved.current)return;const timer=setTimeout(save,3000);return()=>clearTimeout(timer)},[notes,ready,saving]);
 useEffect(()=>{const warn=e=>{if(current.current!==saved.current){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[]);
 const pnl=key=>trade.is_open?'(Open)':trade[key]===null?'Incomplete':money(trade[key],trade.currency);
 return <Modal hideTitle title={`${trade.symbol} · ${trade.direction}`} className="trade-details-modal" busy={saving} onClose={async()=>{if(await save())onClose()}}>
 <div className="trade-detail-banner"><span className="ticker-pill">{trade.symbol}</span><span>{trade.asset_class==='OPT'?`${trade.expiry} · ${Number(trade.strike)} ${trade.put_call==='C'?'Call':'Put'}`:'Stock'}</span>{trade.is_open&&<span className="trade-status">Open</span>}</div>
 <div className={`trade-pnl-hero ${!trade.is_open&&trade.net!==null?(Number(trade.net)<0?'is-loss':'is-gain'):''}`}><span>NET P&amp;L</span><strong>{pnl('net')}</strong><div><span>Gross {pnl('gross')}</span><span>Fees {money(trade.commission,trade.currency)}</span></div></div>
 <div className="trade-detail-tabs" role="tablist" aria-label="Trade details">{tabs.map((name,index)=><button key={name} id={`trade-tab-${name}`} role="tab" aria-selected={activeTab===name} aria-controls={`trade-panel-${name}`} tabIndex={activeTab===name?0:-1} onClick={()=>setActiveTab(name)} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;setActiveTab(tabs[next]);event.currentTarget.parentElement.children[next].focus()}}}>{name}</button>)}</div>
 <div className={`trade-detail-body ${activeTab==='Chart'?'is-chart-view':''}`}>
 <div role="tabpanel" className="trade-chart-layout" id="trade-panel-Chart" aria-labelledby="trade-tab-Chart" hidden={activeTab!=='Chart'}><aside tabIndex={0} className="trade-stats-sidebar" aria-label="Trade statistics"><h3>Stats</h3><dl className="trade-detail-grid">{[['Opened',trade.order_time],['Closed',trade.close_time||'Still open'],['Side',trade.direction],['Quantity',`${Number(trade.quantity)} ${trade.asset_class==='OPT'?'contracts':'shares'}`],['Remaining',Number(trade.remaining)],['Average entry',money(trade.price,trade.currency)],['Average exit',money(trade.exit_price,trade.currency)],['Commissions',money(trade.commission,trade.currency)],['Account',trade.account_alias||trade.account],['Currency',trade.currency],...(trade.asset_class==='OPT'?[['Multiplier',Number(trade.multiplier)]]:[])].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}{['net','gross'].map(key=><div key={key}><dt>{key==='net'?'Net P&L':'Gross P&L'}</dt><dd className={`execution-pnl ${!trade.is_open&&trade[key]!==null?(Number(trade[key])<0?'is-loss':'is-gain'):''}`}>{pnl(key)}</dd></div>)}</dl></aside>
 <div className="trade-chart-main"><React.Suspense fallback={<p role="status">Loading chart…</p>}><TradeChart key={trade.trade_id} trade={trade}/></React.Suspense></div></div>
 <div role="tabpanel" id="trade-panel-Notes" aria-labelledby="trade-tab-Notes" hidden={activeTab!=='Notes'}><section className="trade-notebook"><label htmlFor="trade-journal-notes">Trade journal</label><textarea id="trade-journal-notes" rows="6" maxLength={20000} disabled={!ready} value={notes} placeholder="Your setup, execution, lessons, and what to improve…" onChange={e=>{current.current=e.target.value;setNotes(e.target.value);setStatus('Unsaved changes')}}/><div className="trade-journal-save"><span role="status">{status}</span><button disabled={!ready||saving} onClick={save}>Save</button></div>{error&&<p className="alert error" role="alert">{error}</p>}</section><Attachments date={trade.session_date} tradeKey={trade.trade_id} csrfToken={csrfToken} notify={notify}/></div>
 <div role="tabpanel" id="trade-panel-Executions" aria-labelledby="trade-tab-Executions" hidden={activeTab!=='Executions'}><ExecutionList executions={executions} request={request} onUpdated={onUpdated} notify={notify} beforeDelete={save}/></div>
 </div>
 </Modal>
}
