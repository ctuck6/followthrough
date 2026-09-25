import test from 'node:test';
import assert from 'node:assert/strict';
import {groupPnl,cumulative,instrumentPnl,weekdayPnl,tickerSelection} from './statistics.js';
test('groups tickers without dropping losses or zero results',()=>{assert.deepEqual(groupPnl([{ticker:'AMD',net:'10'},{ticker:'AMD',net:'-15'},{ticker:'TSLA',net:'0'}],'ticker'),[{label:'AMD',net:-5,count:2},{label:'TSLA',net:0,count:1}])});
test('curve accumulates and carries through dates without trades',()=>{assert.deepEqual(cumulative([{date:'2026-09-01',net:'-10'},{date:'2026-09-03',net:'30'}],'2026-09-01','2026-09-03'),[{label:'2026-09-01',net:-10},{label:'2026-09-02',net:-10},{label:'2026-09-03',net:20}])});

test('ticker selection respects search and never falls back to an unrelated ticker',()=>{
 const tickers=[{label:'AMD'},{label:'AMZN'},{label:'TSLA'}];
 assert.equal(tickerSelection(tickers,'amd','TSLA').active,'AMD');
 assert.equal(tickerSelection(tickers,'AM','').active,null);
 assert.equal(tickerSelection(tickers,'AM','AMZN').active,'AMZN');
 assert.equal(tickerSelection(tickers,'missing','AMD').active,null);
 assert.equal(tickerSelection(tickers,'tsl','').active,'TSLA');
});
test('instrument totals isolate a ticker while the overall breakdown includes futures',()=>{
 const rows=[{ticker:'AMD',instrument:'Stocks',net:'20'},{ticker:'AMD',instrument:'Options',net:'-5'},{ticker:'TSLA',instrument:'Options',net:'100'},{ticker:'/ES',instrument:'Futures',net:'-40'}];
 assert.deepEqual(instrumentPnl(rows.filter(r=>r.ticker==='AMD')).map(r=>r.net),[20,-5,0]);
 assert.deepEqual(instrumentPnl(rows).map(r=>r.net),[20,95,-40]);
});
test('weekday totals use closing dates and include weekends in Monday-first order',()=>{
 const result=weekdayPnl([{date:'2026-09-21',net:'10'},{date:'2026-09-21',net:'-15'},{date:'2026-09-27',net:'30'}]);
 assert.equal(result[0].label,'Monday');
 assert.equal(result[0].net,-5);
 assert.equal(result[0].count,2);
 assert.equal(result[1].net,0);
 assert.equal(result[6].label,'Sunday');
 assert.equal(result[6].net,30);
});
