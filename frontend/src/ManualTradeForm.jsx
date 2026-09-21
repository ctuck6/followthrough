import React,{useEffect,useState} from 'react';
import Select from './components/Select.jsx';
import DatePicker from './components/DatePicker.jsx';
export default function ManualTradeForm({asset,date,request,onUpdated,notify}){
 const blank=()=>({id:crypto.randomUUID(),asset,symbol:'',direction:'Long',quantity:'',entry_price:'',exit_price:'',commission:'0',opened_at:`${date}T09:30:00`,closed_at:'',expiry:date,strike:'',put_call:'C',multiplier:asset==='OPT'?'100':'1'});
 const storage=`followthrough-manual-trade-${date}-${asset}`;
 const [form,setForm]=useState(()=>{try{return JSON.parse(localStorage.getItem(storage))||blank()}catch{return blank()}}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{try{localStorage.setItem(storage,JSON.stringify(form))}catch{}},[form,storage]);
 const update=(key,value)=>setForm(f=>({...f,[key]:value}));
 const field=(key,label,extra={})=><label>{label}<input required value={form[key]} onChange={e=>update(key,e.target.value)} {...extra}/></label>;
 function datetime(key,label){const value=form[key];return <div className="manual-datetime"><span>{label}</span><div className="manual-date-controls"><DatePicker value={value.slice(0,10)} label={`${label} date`} onChange={d=>update(key,`${d}T${value.slice(11)}`)} disabled={busy}/><label className="manual-time"><span className="sr-only">{label} time</span><input aria-label={`${label} time`} type="time" required step="1" value={value.slice(11)} onChange={e=>update(key,`${value.slice(0,10)}T${e.target.value}`)}/></label></div></div>}
 async function submit(e){e.preventDefault();setBusy(true);setError('');try{const result=await request('/api/manual-trades/','POST',form);await onUpdated(result,[form.opened_at.slice(0,10)]);notify('Trade saved.');setForm(blank())}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <form className="execution-form manual-trade-form" aria-label={`${asset==='STK'?'Stock':'Option'} trade entry`} onSubmit={submit}>
 <h3 className="form-wide">{asset==='STK'?'Stock trade':'Option trade'}</h3>
 {error&&<p className="alert error form-wide" role="alert">{error}</p>}
 {field('symbol',asset==='STK'?'Ticker':'Underlying ticker',{maxLength:30})}
 <label>Side<Select value={form.direction} onChange={e=>update('direction',e.target.value)}><option>Long</option><option>Short</option></Select></label>
 {field('quantity',asset==='OPT'?'Contracts':'Shares',{type:'number',min:asset==='OPT'?1:.000001,step:asset==='OPT'?1:'any'})}
 {asset==='OPT'&&<>{field('strike','Strike',{type:'number',min:.000001,step:'any'})}<label>Option type<Select value={form.put_call} onChange={e=>update('put_call',e.target.value)}><option value="C">Call</option><option value="P">Put</option></Select></label><div className="manual-datetime"><span>Expiry</span><DatePicker value={form.expiry} label="Option expiry" onChange={d=>update('expiry',d)}/></div>{field('multiplier','Contract multiplier',{type:'number',min:.000001,step:'any'})}</>}
 <div className="manual-trade-block form-wide"><h4>Opening</h4><div className="manual-trade-fields">{datetime('opened_at','Opening')}{field('entry_price','Entry price',{type:'number',min:0,step:'any'})}</div></div>
 <div className="manual-trade-block form-wide"><h4>Closing <small>Optional</small></h4>{form.closed_at?<><div className="manual-trade-fields">{datetime('closed_at','Closing')}{field('exit_price','Exit price',{type:'number',min:0,step:'any'})}</div><button type="button" className="text-button" onClick={()=>setForm(f=>({...f,closed_at:'',exit_price:''}))}>Clear closing details</button></>:<><p className="footnote">Leave the closing date empty while this trade is open.</p><button type="button" onClick={()=>update('closed_at',form.opened_at)}>Add closing date & time</button></>}</div>
 {field('commission','Total commissions ($)',{type:'number',min:0,step:'any'})}
 <p className="footnote form-wide">Enter commissions as a positive cost. {form.closed_at?'This trade will be saved as completed.':'This trade will be saved as open.'}</p>
 <button className="primary" disabled={busy}>{busy?'Saving…':'Save trade'}</button>
 </form>
}
