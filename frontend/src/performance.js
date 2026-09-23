export function performance(trades=[],summaries={},start,end=start){
 const results={};
 const bucket=currency=>results[currency]??=( {net:0,closed:0,wins:0,losses:0,winTotal:0,lossTotal:0,incomplete:0} );
 for(const [date,currencies] of Object.entries(summaries)){
  if(date<start||date>end)continue;
  for(const [currency,s] of Object.entries(currencies)){const b=bucket(currency);b.net+=Number(s.net)||0;b.incomplete+=s.incomplete||0}
 }
 for(const trade of trades){
  const date=trade.close_time?.slice(0,10);
  if(trade.is_open||trade.net==null||!date||date<start||date>end)continue;
  const net=Number(trade.net);if(!Number.isFinite(net))continue;
  const b=bucket(trade.currency);b.closed++;
  if(net>0){b.wins++;b.winTotal+=net}else if(net<0){b.losses++;b.lossTotal-=net}
 }
 return Object.entries(results).sort(([a],[b])=>a.localeCompare(b)).map(([currency,b])=>({...b,currency,winRate:b.closed?b.wins/b.closed*100:null,ratio:b.losses?(b.wins?b.winTotal/b.wins:0)/(b.lossTotal/b.losses):b.wins?Infinity:null}));
}
export function ruleFollowing(checks){const applicable=checks.filter(c=>c.status!=='na');return {followed:applicable.filter(c=>c.status==='followed').length,total:applicable.length}}
