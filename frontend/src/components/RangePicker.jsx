import React,{useState} from 'react';
import Modal from './Modal.jsx';
import {dateKey,monthCells,presetRange,selectRangeDate} from '../calendar.js';
export const rangePresets=[['today','Today'],['week','This Week'],['current-month','This Month'],['quarter','This Quarter'],['ytd','YTD']];
const shift=(month,n)=>{const [y,m]=month.split('-').map(Number);return dateKey(new Date(y,m-1+n,1)).slice(0,7)};
const title=month=>new Date(`${month}-01T12:00:00`).toLocaleDateString('en-US',{month:'long',year:'numeric'});
export default function RangePicker({value,period,today,onApply,onClose}){
 const [start,setStart]=useState(value[0]),[end,setEnd]=useState(value[1]),[hover,setHover]=useState(''),[choice,setChoice]=useState(period);
 const latest=today.slice(0,7);
 const [left,setLeft]=useState(value[0].slice(0,7)<value[1].slice(0,7)?value[0].slice(0,7):shift(value[1].slice(0,7),-1));
 const [right,setRight]=useState(value[1].slice(0,7));
 const through=end||(hover>=start?hover:start);
 function choose(date){const range=selectRangeDate(start,end,date,today);setStart(range[0]);setEnd(range[1]);setHover('');setChoice('custom')}
 function preset(key){const [a,b]=presetRange(key,today);setStart(a);setEnd(b);setHover('');setChoice(key);setRight(b.slice(0,7));setLeft(a.slice(0,7)<b.slice(0,7)?a.slice(0,7):shift(b.slice(0,7),-1))}
 function calendar(month,side){const update=side==='left'?setLeft:setRight;const prev=shift(month,-1),next=shift(month,1);return <section className="range-month" aria-label={`${side==='left'?'First':'Second'} calendar`}>
 <div className="range-month-heading"><button type="button" aria-label={`Previous month in ${side} calendar`} disabled={side==='right'&&prev<=left} onClick={()=>update(prev)}>‹</button><h3>{title(month)}</h3><button type="button" aria-label={`Next month in ${side} calendar`} disabled={next>latest||(side==='left'&&next>=right)} onClick={()=>update(next)}>›</button></div>
 <div className="range-day-grid">{['Su','Mo','Tu','We','Th','Fr','Sa'].map(d=><span className="picker-weekday" key={d}>{d}</span>)}{monthCells(month).map((date,i)=>date?<button key={date} type="button" disabled={date>today||Boolean(start&&!end&&date<start)} aria-label={date} aria-pressed={Boolean(start&&date>=start&&date<=through)} aria-current={date===today?'date':undefined} className={`range-day ${start&&date>=start&&date<=through?'range-included':''} ${date===start?'range-start':''} ${date===through?'range-end':''} ${date===start||date===end?'range-selected':''}`} onMouseEnter={()=>{if(start&&!end&&date>=start&&date<=today)setHover(date)}} onFocus={()=>{if(start&&!end&&date>=start&&date<=today)setHover(date)}} onClick={()=>choose(date)}><span>{Number(date.slice(-2))}</span></button>:<span key={`blank-${i}`}/>)}</div>
 </section>}
 return <Modal title="Date range" className="range-picker-modal" onClose={onClose}><div className="range-picker-layout"><div className="range-custom"><div className="range-selection" aria-live="polite"><span>{start||'Start date'}</span><span aria-hidden="true">→</span><span>{end||'End date'}</span></div><div className="range-calendars">{calendar(left,'left')}{calendar(right,'right')}</div></div><div className="range-presets" role="group" aria-label="Date range presets">{rangePresets.map(([key,label])=><button type="button" key={key} aria-pressed={choice===key} onClick={()=>preset(key)}>{label}</button>)}</div></div><div className="modal-actions"><button type="button" onClick={onClose}>Cancel</button><button type="button" className="primary" disabled={!start||!end||end<start||end>today} onClick={()=>onApply([start,end],choice)}>Go</button></div></Modal>
}
