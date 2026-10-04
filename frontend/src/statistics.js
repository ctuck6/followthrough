export function groupPnl(rows,key){const groups=new Map();for(const r of rows){const label=r[key],old=groups.get(label)||{label,net:0,count:0};old.net+=Number(r.net);old.count++;groups.set(label,old)}return [...groups.values()]}
export function cumulative(rows,start,end){const dates=new Map(groupPnl(rows,'date').map(r=>[r.label,r.net]));let total=0;const output=[];for(let d=new Date(`${start}T12:00:00Z`);d<=new Date(`${end}T12:00:00Z`);d.setUTCDate(d.getUTCDate()+1)){const label=d.toISOString().slice(0,10);total+=dates.get(label)||0;output.push({label,net:total})}return output}

export function tickerSelection(tickers, search, selected) {
 const query=search.trim().toUpperCase();
 const matches=tickers.filter(r=>r.label.toUpperCase().includes(query));
 const active=matches.find(r=>r.label===selected)?.label
  || matches.find(r=>r.label.toUpperCase()===query)?.label
  || ((!query || matches.length===1)?matches[0]?.label:null)
  || null;
 return {matches,active};
}
export function instrumentPnl(rows) {
 const groups=groupPnl(rows,'instrument');
 return ['Stocks','Options','Futures'].map(label=>groups.find(r=>r.label===label)||{label,net:0,count:0});
}
export function weekdayPnl(rows) {
 const days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
 const groups=groupPnl(rows.map(r=>({...r,weekday:days[new Date(`${r.date}T12:00:00Z`).getUTCDay()]})),'weekday');
 return [...days.slice(1),days[0]].map(label=>groups.find(r=>r.label===label)||{label,net:0,count:0});
}

export function sessionHours(rows) {
 const clock=m=>`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
 return [['Premarket',240,570],['Regular session',570,960],['After hours',960,1200],['Overnight',0,240],['Overnight',1200,1440]].reduce((sessions,[title,start,end])=>{
  let session=sessions.find(s=>s.title===title);
  if(!session){session={title,rows:[]};sessions.push(session)}
  for(let minute=start;minute<end;){
   const next=Math.min(end,(Math.floor(minute/60)+1)*60);
   const trades=rows.filter(r=>{const m=r.entry_minute??Number(r.hour)*60;return m>=minute&&m<next});
   session.rows.push({label:`${clock(minute)}–${clock(next)}`,net:trades.reduce((sum,r)=>sum+Number(r.net),0),count:trades.length,trades});
   minute=next;
  }
  return sessions;
 },[]).filter(s=>s.title!=='Overnight'||s.rows.some(r=>r.count));
}
