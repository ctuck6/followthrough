import test from 'node:test';
import assert from 'node:assert/strict';
import {parseTradeCsv} from './tradeCsv.js';
test('quoted CSV, BOM, CRLF and aliases',()=>{
 const rows=parseTradeCsv('\uFEFFticker,direction,net pnl,notes,date\r\nES,short,-20.50,"A, B ""test""",2026-09-20\r\n','2026-09-20');
 assert.deepEqual(rows,[{symbol:'ES',side:'Short',pnl:'-20.50',notes:'A, B "test"'}]);
});
test('reject invalid financial values and mismatched dates without partial import',()=>{
 for(const amount of ['NaN','Infinity','1.001','1e3',''])assert.throws(()=>parseTradeCsv(`symbol,side,pnl\nES,Long,${amount}`,'2026-09-20'));
 assert.throws(()=>parseTradeCsv('symbol,side,pnl,date\nES,Long,2,2026-09-19','2026-09-20'),/Date must match/);
 assert.throws(()=>parseTradeCsv('symbol,side,pnl\nES,Buy,2','2026-09-20'),/Long or Short/);
 assert.throws(()=>parseTradeCsv('symbol,side,pnl\nES,Long,2\nNQ,Short,invalid','2026-09-20'),/Row 3/);
});
test('handles multiline notes and validates malformed CSV',()=>{
 assert.equal(parseTradeCsv('symbol,side,pnl,notes\nES,Long,0,"line 1\nline 2"','2026-09-20')[0].notes,'line 1\nline 2');
 assert.throws(()=>parseTradeCsv('symbol,side,pnl\n"ES,Long,1','2026-09-20'),/closing quote/);
 assert.throws(()=>parseTradeCsv('symbol,side,pnl\nES,Long,2,extra','2026-09-20'),/Column count/);
});
