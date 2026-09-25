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
