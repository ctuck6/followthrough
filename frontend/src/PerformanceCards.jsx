import React from 'react';
import {performance} from './performance.js';
export default function PerformanceCards({trades=[],summaries={},start,end=start,includePnl=false,average=false}){
 const stats=performance(trades,summaries,start,end);
 const cards=[...(includePnl?[['pnl','NET P&L','↗']]:[]),['rate',average?'AVERAGE WIN RATE':'WIN RATE','◎'],['ratio',average?'AVERAGE WIN/LOSS RATIO':'WIN/LOSS RATIO','⇄']];
 return <div className={`performance-cards ${includePnl?'has-pnl':''}`}>{cards.map(([key,label,icon])=><section className={`performance-card performance-${key}`} key={key}><div className="performance-heading"><span className="eyebrow">{label}</span><span className="performance-icon" aria-hidden="true">{icon}</span></div>{!stats.length?<strong className="performance-value">—</strong>:stats.map(s=><div key={s.currency} className="performance-result"><strong className={`performance-value ${key==='pnl'?(s.net<0?'is-loss':'is-gain'):''}`}>{key==='pnl'?new Intl.NumberFormat('en-US',{style:'currency',currency:s.currency}).format(s.net):key==='rate'?(s.winRate==null?'—':`${s.winRate.toFixed(1)}%`):s.ratio==null?'—':s.ratio===Infinity?'∞':`${s.ratio.toFixed(2)} : 1`}</strong><small>{s.currency}</small>{key==='pnl'&&s.incomplete>0&&<small>Incomplete — missing cost basis</small>}</div>)}</section>)}</div>
}
