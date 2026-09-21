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

test('presets use current date and calendar boundaries',async()=>{
 const {presetRange}=await import('./calendar.js');
 assert.deepEqual(presetRange('today','2026-09-21'),['2026-09-21','2026-09-21']);
 assert.deepEqual(presetRange('week','2026-09-21'),['2026-09-20','2026-09-21']);
 assert.deepEqual(presetRange('current-month','2026-09-21'),['2026-09-01','2026-09-21']);
 assert.deepEqual(presetRange('quarter','2026-09-21'),['2026-07-01','2026-09-21']);
 assert.deepEqual(presetRange('ytd','2026-09-21'),['2026-01-01','2026-09-21']);
});
test('range selection rejects backwards and future dates and restarts only after completion',async()=>{
 const {selectRangeDate}=await import('./calendar.js');
 assert.deepEqual(selectRangeDate('2026-08-20','','2026-08-10','2026-09-21'),['2026-08-20','']);
 assert.deepEqual(selectRangeDate('2026-08-20','','2026-09-10','2026-09-21'),['2026-08-20','2026-09-10']);
 assert.deepEqual(selectRangeDate('2026-08-20','2026-09-10','2026-09-15','2026-09-21'),['2026-09-15','']);
 assert.deepEqual(selectRangeDate('2026-08-20','','2026-09-22','2026-09-21'),['2026-08-20','']);
});

test('consistency streak skips weekends and allows today to remain unfinished',async()=>{
 const {consistencyStreak}=await import('./calendar.js');
 const reviewed=date=>({date,checks:[{status:'followed'},{status:'broken'},{status:'na'}]});
 const days=['2026-09-17','2026-09-18'].map(reviewed);
 assert.equal(consistencyStreak(days,'2026-09-21'),2);
 assert.equal(consistencyStreak(days,'2026-09-20'),2);
 assert.equal(consistencyStreak([...days,reviewed('2026-09-21')],'2026-09-21'),3);
 assert.equal(consistencyStreak(days,'2026-09-22'),0);
});
test('consistency streak requires every rule and stops at a missed weekday',async()=>{
 const {consistencyStreak}=await import('./calendar.js');
 const reviewed=date=>({date,checks:[{status:'na'}]});
 assert.equal(consistencyStreak([reviewed('2026-09-18'),reviewed('2026-09-16')],'2026-09-21'),1);
 assert.equal(consistencyStreak([{date:'2026-09-18',checks:[]}],'2026-09-21'),0);
 assert.equal(consistencyStreak([{date:'2026-09-18',checks:[{status:'followed'},{status:'pending'}]}],'2026-09-21'),0);
});
