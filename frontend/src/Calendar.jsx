import DatePicker from './components/DatePicker.jsx';
import Select from './components/Select.jsx';
import React, {useState} from 'react';
import {averageGrade, dateKey, monthCells, timeframeRange} from './calendar.js';

export default function Calendar({days, today, onOpen}) {
  const [month,setMonth]=useState(today.slice(0,7));
  const [period,setPeriod]=useState('month');
  const [custom,setCustom]=useState([today.slice(0,7)+'-01',today]);
  const [start,end]=period==='custom'?custom:timeframeRange(period,month,today);
  const valid=Boolean(start&&end&&start<=end);
  const average=averageGrade(days,valid?start:'9999',valid?end:'0000');
  const byDate=new Map(days.map(day=>[day.date,day]));
  const title=new Date(`${month}-01T12:00:00`).toLocaleDateString('en-US',{month:'long',year:'numeric'});
  function move(delta){const [y,m]=month.split('-').map(Number);setMonth(dateKey(new Date(y,m-1+delta,1)).slice(0,7));}
  return <div className="calendar-view">
    <section className="panel calendar-summary" aria-label="Average execution grade">
      <div><span className="eyebrow">AVERAGE EXECUTION GRADE</span><div className="grade-number" aria-live="polite">{average.letter}<span>{average.score===null?'No graded days':`${average.score}% adherence`}</span></div><p className="subtle">{average.count} graded {average.count===1?'day':'days'} · Each day counts equally</p></div>
      <div className="range-controls"><label>Average timeframe<Select popover aria-label="Average timeframe" value={period} onChange={e=>setPeriod(e.target.value)}><option value="month">Displayed month</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="custom">Custom range</option></Select></label>
      {period==='custom'&&<div className="custom-range"><div><span className="field-label">From</span><DatePicker label="Start date" value={custom[0]} onChange={value=>setCustom([value,custom[1]])}/></div><div><span className="field-label">Through</span><DatePicker label="End date" value={custom[1]} onChange={value=>setCustom([custom[0],value])}/></div></div>}
      {valid?<small>{start} through {end} · Inclusive</small>:<small className="negative" role="alert">Choose a valid range with the end on or after the start.</small>}
      <small>Saved grades only. Pending and unlogged days are excluded.</small></div>
    </section>
    <section className="panel calendar-panel" aria-label="Monthly grade calendar"><div className="calendar-toolbar"><h2 aria-live="polite">{title}</h2><div className="month-controls"><button aria-label="Previous month" onClick={()=>move(-1)}>←</button><button onClick={()=>setMonth(today.slice(0,7))}>This month</button><button aria-label="Next month" onClick={()=>move(1)}>→</button></div></div>
      <div className="calendar-grid">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=><div className="weekday" key={d}>{d}</div>)}{monthCells(month).map((date,i)=>{
        if(!date)return <div key={`empty-${i}`} className="calendar-spacer" aria-hidden="true"/>;
        const day=byDate.get(date),graded=day&&day.score!==null,grade=graded?day.grade:null;
        return <button key={date} className={`calendar-day ${grade?`grade-${grade}`:''} ${date===today?'is-today':''} ${valid&&date>=start&&date<=end?'in-range':''}`} aria-label={`${date}: ${graded?`Grade ${grade}, ${day.score}%`:day?'Review pending':'No review'}. Open daily review`} aria-current={date===today?'date':undefined} onClick={()=>onOpen(date)}><span className="calendar-date">{Number(date.slice(-2))}{date===today&&<span className="today-label">Today</span>}</span><strong className="calendar-letter">{grade||'—'}</strong><span className="calendar-detail">{graded?`${day.score}%`:day?'Pending':'No review'}</span></button>;
      })}</div>
      <div className="calendar-legend" aria-label="Grade colors">{[['A','90–100%'],['B','80–89%'],['C','70–79%'],['D','D / F · below 70%']].map(([grade,range])=><span key={grade}><i className={`grade-${grade}`} aria-hidden="true"/>{grade==='D'?range:`${grade} · ${range}`}</span>)}</div>
      <p className="footnote">Select a day to open its review. Outlined dates are in your average timeframe.</p>
    </section>
  </div>;
}
