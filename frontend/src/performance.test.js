import test from 'node:test';
import assert from 'node:assert/strict';
import {performance,ruleFollowing} from './performance.js';
const trade=(net,date='2026-09-21',extra={})=>({net,close_time:`${date} 10:00:00`,currency:'USD',is_open:false,...extra});
test('performance uses closed trades in range, includes break-even and separates currencies',()=>{
 const result=performance([trade('100'),trade('-50'),trade('0'),trade('999','2026-09-21',{is_open:true}),trade(null),trade('500','2026-09-20'),trade('20','2026-09-21',{currency:'CAD'})],{'2026-09-21':{USD:{net:'50'}}},'2026-09-21');
 const usd=result.find(s=>s.currency==='USD');assert.equal(usd.closed,3);assert.ok(Math.abs(usd.winRate-100/3)<1e-10);assert.equal(usd.ratio,2);assert.equal(usd.net,50);assert.equal(result.find(s=>s.currency==='CAD').winRate,100);
});
test('ratios handle no trades, no losses, and no wins',()=>{
 assert.deepEqual(performance([],{},'2026-09-21'),[]);
 assert.equal(performance([trade('10')],{},'2026-09-21')[0].ratio,Infinity);
 assert.equal(performance([trade('-10')],{},'2026-09-21')[0].ratio,0);
 assert.equal(performance([trade('0')],{},'2026-09-21')[0].ratio,null);
});
test('timeframe rates pool trades and attribute overnight trades to closing date',()=>{
 const trades=[trade('100','2026-09-20'),trade('-20'),trade('-30')];
 assert.equal(performance(trades,{},'2026-09-20','2026-09-21')[0].ratio,4);
 assert.equal(performance(trades,{},'2026-09-21')[0].closed,2);
});
test('rules followed excludes not applicable and does not count reviewed broken rules',()=>{
 assert.deepEqual(ruleFollowing(['followed','broken','pending','na'].map(status=>({status}))),{followed:1,total:3});
 assert.deepEqual(ruleFollowing([{status:'na'}]),{followed:0,total:0});
});
