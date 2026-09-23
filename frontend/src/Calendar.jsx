import PerformanceCards from './PerformanceCards.jsx';
import RangePicker, {rangePresets} from './components/RangePicker.jsx';
import React, {useState} from 'react';
import {averageGrade, dateKey, monthCells, presetRange, consistencyStreak, fullyReviewed} from './calendar.js';

export default function Calendar({days, trades=[], summaries={}, today, onOpen}) {
  const [month,setMonth]=useState(today.slice(0,7));
  const [period,setPeriod]=useState('current-month');
  const [custom,setCustom]=useState([today.slice(0,7)+'-01',today]);
  const [pickerOpen,setPickerOpen]=useState(false);
  const [start,end]=period==='custom'?custom:presetRange(period,today);
  const valid=Boolean(start&&end&&start<=end);
  const average=averageGrade(days,valid?start:'9999',valid?end:'0000');
  const streak=consistencyStreak(days,today);
  const byDate=new Map(days.map(day=>[day.date,day]));
  const title=new Date(`${month}-01T12:00:00`).toLocaleDateString('en-US',{month:'long',year:'numeric'});
  function move(delta){const [y,m]=month.split('-').map(Number);setMonth(dateKey(new Date(y,m-1+delta,1)).slice(0,7));}
  return <div className="calendar-view">
    <section className="panel calendar-summary" aria-label="Average execution grade">
      <div className="calendar-grade-and-streak"><div><span className="eyebrow">AVERAGE EXECUTION GRADE</span><div className="grade-number" aria-live="polite">{average.letter}<span>{average.score===null?'No graded days':`${average.score}% adherence`}</span></div><p className="subtle">{average.count} graded {average.count===1?'day':'days'} · Each day counts equally</p></div><div className="consistency-streak" role="status" aria-label={`Consistency streak: ${streak} trading ${streak===1?'day':'days'}`}><span className="eyebrow">CONSISTENCY STREAK</span><div className="streak-value"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg><strong>{streak}</strong></div><span className="streak-unit">{streak===1?'trading day':'trading days'}</span></div></div>
      <div className="range-controls"><span className="field-label">Average timeframe</span><button type="button" className="date-picker-trigger" aria-haspopup="dialog" aria-label="Choose average timeframe" onClick={()=>setPickerOpen(true)}>{period==='custom'?'Custom range':rangePresets.find(([key])=>key===period)?.[1]} <svg className="date-picker-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button><small>{start} → {end}</small></div>
      {pickerOpen&&<RangePicker value={[start,end]} period={period} today={today} onClose={()=>setPickerOpen(false)} onApply={(range,key)=>{setCustom(range);setPeriod(key);setPickerOpen(false)}}/>}
    </section>
    <PerformanceCards trades={trades} summaries={summaries} start={start} end={end} includePnl average/>
    <section className="panel calendar-panel" aria-label="Monthly grade calendar"><div className="calendar-toolbar"><h2 aria-live="polite">{title}</h2><div className="month-controls"><button aria-label="Previous month" onClick={()=>move(-1)}>←</button><button onClick={()=>setMonth(today.slice(0,7))}>This month</button><button aria-label="Next month" onClick={()=>move(1)}>→</button></div></div>
      <div className="calendar-grid">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=><div className="weekday" key={d}>{d}</div>)}{monthCells(month).map((date,i)=>{
        if(!date)return <div key={`empty-${i}`} className="calendar-spacer" aria-hidden="true"/>;
        const day=byDate.get(date),graded=day&&typeof day.score==='number',grade=graded?day.grade:null;
        const reviewed=fullyReviewed(day);
        const pnl=Object.entries(summaries[date]||{}).map(([currency,summary])=>({currency,...summary,display:new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits:2}).format(Number(summary.net))}));
        return <button key={date} className={`calendar-day ${grade?`grade-${grade}`:''} ${date===today?'is-today':''} ${valid&&date>=start&&date<=end?'in-range':''}`} aria-label={`${date}${grade?`: Grade ${grade}, ${day.score}%`:''}${pnl.length?`, Net P&L ${pnl.map(p=>p.incomplete?'Incomplete':p.display).join(', ')}`:''}${reviewed?', Reviewed':''}. Open daily review`} aria-current={date===today?'date':undefined} onClick={()=>onOpen(date)}><span className="calendar-date">{Number(date.slice(-2))}{date===today&&<span className="today-label">Today</span>}</span><span className="calendar-day-result"><strong className="calendar-letter">{grade||''}</strong>{pnl.map(p=><span key={p.currency} className={`calendar-pnl ${Number(p.net)<0?'is-loss':Number(p.net)>0?'is-gain':''}`} title={`Net P&L · ${p.currency}`}>{p.incomplete?'Incomplete':p.display}</span>)}</span>{reviewed&&<span className="calendar-reviewed" title="Reviewed"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg></span>}</button>;
      })}</div>
      <div className="calendar-legend" aria-label="Grade colors">{[['A','90–100%'],['B','80–89%'],['C','70–79%'],['D','D / F · below 70%']].map(([grade,range])=><span key={grade}><i className={`grade-${grade}`} aria-hidden="true"/>{grade==='D'?range:`${grade} · ${range}`}</span>)}</div>
      <p className="footnote">Select a day to open its review. Outlined dates are in your average timeframe.</p>
    </section>
  </div>;
}
