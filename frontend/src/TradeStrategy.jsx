import React,{forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import Select from './components/Select.jsx';
export default forwardRef(function TradeStrategy({trade,request,onBusyChange},ref){
 const [catalog,setCatalog]=useState([]),[value,setValue]=useState({strategy_id:null,checked:[]}),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const current=useRef(value),saved=useRef(value),pending=useRef(null);
 const url=`/api/trades/${trade.trade_id}/strategy/`;
 useEffect(()=>{const controller=new AbortController();fetch(url,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('Could not load trade strategy.');return r.json()}).then(d=>{setCatalog(d.strategies);const v={strategy_id:d.strategy_id,checked:d.checked};current.current=saved.current=v;setValue(v);setReady(true)}).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return()=>controller.abort()},[url]);
 async function save(){if(pending.current)return pending.current;if(current.current===saved.current)return true;const snapshot=current.current;setBusy(true);onBusyChange(true);setError('');const operation=(async()=>{try{await request(url,'PUT',snapshot);saved.current=snapshot;return true}catch(e){setError(e.message);return false}finally{pending.current=null;setBusy(false);onBusyChange(false)}})();pending.current=operation;return operation}
 useImperativeHandle(ref,()=>({flush:save}));
 useEffect(()=>{const warn=e=>{if(current.current!==saved.current){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[]);
 function change(next){current.current=next;setValue(next);save()}
 const strategy=catalog.find(s=>s.id===value.strategy_id);
 return <section className="trade-strategy"><label>Strategy<Select disabled={!ready||busy} value={value.strategy_id??''} onChange={e=>change({strategy_id:e.target.value?Number(e.target.value):null,checked:[]})}><option value="">No strategy</option>{catalog.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</Select></label>{strategy&&<div className="strategy-checklist">{strategy.criteria.map(c=><label key={c.id}><input type="checkbox" disabled={busy} checked={value.checked.includes(c.id)} onChange={e=>change({...value,checked:e.target.checked?[...value.checked,c.id]:value.checked.filter(id=>id!==c.id)})}/><span>{c.text}</span></label>)}</div>}{busy&&<span role="status">Saving…</span>}{error&&<div className="alert error" role="alert">{error}{ready&&<button onClick={save}>Retry save</button>}</div>}</section>
});
