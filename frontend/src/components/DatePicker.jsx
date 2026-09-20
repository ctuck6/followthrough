import React, {useState, useRef} from 'react';
import Popover from './Popover.jsx';
import Select from './Select.jsx';
import {dateKey, monthCells} from '../calendar.js';

const months=Array.from({length:12},(_,i)=>new Date(2026,i,1).toLocaleDateString('en-US',{month:'long'}));
export default function DatePicker({value, onChange, label='Trading day', disabled=false}) {
  const anchor=useRef(null);
  const [open,setOpen]=useState(false),[month,setMonth]=useState(value.slice(0,7));
  const [year,index]=month.split('-').map(Number);
  const today=dateKey(new Date());
  const display=new Date(`${value}T12:00:00`).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
  function move(delta){setMonth(dateKey(new Date(year,index-1+delta,1)).slice(0,7))}
  function choose(date){setOpen(false);anchor.current?.focus();onChange(date)}
  function keyboard(event,date){
    const offsets={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};
    if(!(event.key in offsets))return;
    event.preventDefault();const next=new Date(`${date}T12:00:00`);next.setDate(next.getDate()+offsets[event.key]);const key=dateKey(next);
    setMonth(key.slice(0,7));requestAnimationFrame(()=>document.querySelector(`[data-picker-date="${key}"]`)?.focus());
  }
  return <><button ref={anchor} type="button" className="date-picker-trigger" disabled={disabled} aria-label={`${label}: ${display}`} aria-haspopup="dialog" aria-expanded={open} onClick={()=>{setMonth(value.slice(0,7));setOpen(true)}}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18"/></svg><span>{display}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>
  </button>{open&&<Popover anchor={anchor} label={`Select ${label.toLowerCase()}`} className="date-picker-popover" onClose={()=>setOpen(false)}>
    <div className="picker-controls"><button type="button" aria-label="Previous month" onClick={()=>move(-1)}>‹</button><Select aria-label="Month" value={index} onChange={e=>setMonth(`${year}-${String(e.target.value).padStart(2,'0')}`)}>{months.map((name,i)=><option key={name} value={i+1}>{name}</option>)}</Select><label className="sr-only" htmlFor="picker-year">Year</label><input id="picker-year" aria-label="Year" type="number" min="1900" max="2100" value={year} onChange={e=>{const y=Number(e.target.value);if(y>=1900&&y<=2100)setMonth(`${y}-${String(index).padStart(2,'0')}`)}}/><button type="button" aria-label="Next month" onClick={()=>move(1)}>›</button></div>
    <p className="sr-only" aria-live="polite">{months[index-1]} {year}</p>
    <div className="picker-grid">{['Su','Mo','Tu','We','Th','Fr','Sa'].map(d=><span className="picker-weekday" key={d}>{d}</span>)}{monthCells(month).map((date,i)=>date?<button type="button" key={date} data-picker-date={date} autoFocus={date===value} className={`picker-day ${date===value?'selected':''} ${date===today?'today':''}`} aria-label={new Date(`${date}T12:00:00`).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'})} aria-pressed={date===value} aria-current={date===today?'date':undefined} onKeyDown={e=>keyboard(e,date)} onClick={()=>choose(date)}>{Number(date.slice(-2))}</button>:<span key={`blank-${i}`}/>)}</div>
    <div className="picker-footer"><button type="button" onClick={()=>choose(today)}>Today</button><button type="button" onClick={()=>setOpen(false)}>Cancel</button></div>
  </Popover>}</>;
}
