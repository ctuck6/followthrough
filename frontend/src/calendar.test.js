import test from 'node:test';
import assert from 'node:assert/strict';
import {averageGrade, monthCells, timeframeRange} from './calendar.js';
test('calendar aligns weekdays and supports leap years',()=>{
 const leap=monthCells('2024-02');assert.equal(leap[4],'2024-02-01');assert.equal(leap.filter(Boolean).length,29);assert.equal(leap.length%7,0);
 assert.equal(monthCells('2026-02').filter(Boolean).length,28);
});
test('average includes range boundaries and excludes incomplete days',()=>{
 const days=[{date:'2026-09-01',score:100},{date:'2026-09-02',score:0},{date:'2026-09-03',score:null},{date:'2026-08-31',score:100}];
 assert.deepEqual(averageGrade(days,'2026-09-01','2026-09-03'),{score:50,letter:'F',count:2});
 assert.deepEqual(averageGrade(days,'2026-10-01','2026-10-31'),{score:null,letter:'—',count:0});
});
test('rolling ranges include today and cross year boundaries',()=>{
 assert.deepEqual(timeframeRange('7','2026-01','2026-01-03'),['2025-12-28','2026-01-03']);
 assert.deepEqual(timeframeRange('30','2026-01','2026-01-03'),['2025-12-05','2026-01-03']);
 assert.deepEqual(timeframeRange('month','2024-02','2026-01-03'),['2024-02-01','2024-02-29']);
});
