import React,{useEffect,useState} from 'react';
import Select from './components/Select.jsx';
import DatePicker from './components/DatePicker.jsx';
import TimePicker from './components/TimePicker.jsx';
export default function ManualTradeForm({asset,date,request,onUpdated,notify}){
 const blank=()=>({id:crypto.randomUUID(),asset,symbol:'',side:'BUY',quantity:'',price:'',commission:'0',executed_at:`${date}T09:30:00`,expiry:date,strike:'',put_call:'C',multiplier:asset==='OPT'?'100':asset==='FUT'?'':'1'});
 const storage=`followthrough-manual-fill-${date}-${asset}`;
 const [form,setForm]=useState(()=>{try{return JSON.parse(localStorage.getItem(storage))||blank()}catch{return blank()}}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{try{localStorage.setItem(storage,JSON.stringify(form))}catch{}},[form,storage]);
 const update=(key,value)=>setForm(f=>({...f,[key]:value}));
 const field=(key,label,extra={})=><label>{label}<input required disabled={busy} value={form[key]} onChange={e=>update(key,e.target.value)} {...extra}/></label>;
 async function submit(e){e.preventDefault();setBusy(true);setError('');try{const result=await request('/api/manual-executions/','POST',{...form,multiplier:asset==='OPT'?'100':asset==='FUT'?form.multiplier:'1'});await onUpdated(result,[form.executed_at.slice(0,10)]);notify('Execution saved.');setForm(blank())}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <form className="execution-form manual-trade-form" aria-label={`${asset==='STK'?'Stock':asset==='FUT'?'Future':'Option'} execution entry`} onSubmit={submit}>
 <h3 className="form-wide">{asset==='STK'?'Stock execution':asset==='FUT'?'Future execution':'Option execution'}</h3>
 {error&&<p className="alert error form-wide" role="alert">{error}</p>}
 {field('symbol',asset==='STK'?'Ticker':asset==='FUT'?'Contract symbol (e.g. /MNQU26)':'Underlying ticker',{maxLength:30})}
 <label>Action<Select disabled={busy} value={form.side} onChange={e=>update('side',e.target.value)}><option value="BUY">Buy</option><option value="SELL">Sell</option></Select></label>
 {field('quantity',asset!=='STK'?'Contracts':'Shares',{type:'number',min:asset!=='STK'?1:.000001,step:asset!=='STK'?1:'any'})}
 {asset==='OPT'&&<>{field('strike','Strike',{type:'number',min:.000001,step:'any'})}<label>Option type<Select disabled={busy} value={form.put_call} onChange={e=>update('put_call',e.target.value)}><option value="C">Call</option><option value="P">Put</option></Select></label><div className="manual-datetime"><span>Expiry</span><DatePicker disabled={busy} value={form.expiry} label="Option expiry" onChange={d=>update('expiry',d)}/></div></>}
 <div className="manual-datetime"><span>Execution date</span><DatePicker disabled={busy} value={form.executed_at.slice(0,10)} label="Execution date" onChange={d=>update('executed_at',`${d}T${form.executed_at.slice(11)}`)}/></div>
 <div className="manual-datetime"><span>Execution time</span><TimePicker disabled={busy} value={form.executed_at.slice(11)} label="Execution time" onChange={t=>update('executed_at',`${form.executed_at.slice(0,10)}T${t}`)}/></div>
 {asset==='FUT'&&field('multiplier','Contract multiplier ($ per point)',{type:'number',min:.000001,step:'any'})}{field('price','Fill price',{type:'number',min:asset==='FUT'?undefined:0,step:'any'})}{field('commission','Commissions ($)',{type:'number',min:0,step:'any'})}
 <div className="form-wide"><button className="primary" disabled={busy}>{busy?'Saving…':'Save execution'}</button></div>
 </form>
}
