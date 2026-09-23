import test from 'node:test';
import assert from 'node:assert/strict';
import {groupPnl,cumulative} from './statistics.js';
test('groups tickers without dropping losses or zero results',()=>{assert.deepEqual(groupPnl([{ticker:'AMD',net:'10'},{ticker:'AMD',net:'-15'},{ticker:'TSLA',net:'0'}],'ticker'),[{label:'AMD',net:-5,count:2},{label:'TSLA',net:0,count:1}])});
test('curve accumulates and carries through dates without trades',()=>{assert.deepEqual(cumulative([{date:'2026-09-01',net:'-10'},{date:'2026-09-03',net:'30'}],'2026-09-01','2026-09-03'),[{label:'2026-09-01',net:-10},{label:'2026-09-02',net:-10},{label:'2026-09-03',net:20}])});
