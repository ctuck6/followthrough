import React,{useEffect,useRef,useState} from 'react';
import Modal from './components/Modal.jsx';
import Attachments from './Attachments.jsx';
const money=(v,c)=>v===null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:c}).format(Number(v));
export default function TradeDetails({trade,request,csrfToken,notify,onClose}){
 const [notes,setNotes]=useState(''),[ready,setReady]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState('Loading journal…');
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
 <dl className="trade-detail-grid">{[['Opened',trade.order_time],['Closed',trade.close_time||'Still open'],['Side',trade.direction],['Quantity',`${Number(trade.quantity)} ${trade.asset_class==='OPT'?'contracts':'shares'}`],['Remaining',Number(trade.remaining)],['Average entry',money(trade.price,trade.currency)],['Average exit',money(trade.exit_price,trade.currency)],['Commissions',money(trade.commission,trade.currency)],['Account',trade.account_alias||trade.account],['Currency',trade.currency],...(trade.asset_class==='OPT'?[['Multiplier',Number(trade.multiplier)]]:[])].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}{['net','gross'].map(key=><div key={key}><dt>{key==='net'?'Net P&L':'Gross P&L'}</dt><dd className={`execution-pnl ${!trade.is_open&&trade[key]!==null?(Number(trade[key])<0?'is-loss':'is-gain'):''}`}>{pnl(key)}</dd></div>)}</dl>
 <section className="trade-notebook"><label htmlFor="trade-journal-notes">Trade journal</label><textarea id="trade-journal-notes" rows="6" maxLength={20000} disabled={!ready} value={notes} placeholder="Your setup, execution, lessons, and what to improve…" onChange={e=>{current.current=e.target.value;setNotes(e.target.value);setStatus('Unsaved changes')}}/><div className="trade-journal-save"><span role="status">{status}</span><button disabled={!ready||saving} onClick={save}>Save</button></div>{error&&<p className="alert error" role="alert">{error}</p>}</section>
 <Attachments date={trade.session_date} tradeKey={trade.trade_id} csrfToken={csrfToken} notify={notify}/>
 </Modal>
}
