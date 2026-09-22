import test from 'node:test';
import assert from 'node:assert/strict';
import {executionMarkers} from './chartMarkers.js';
test('fills align to their minute, preserving multiple fills and direction',()=>{
 const markers=executionMarkers([{time:120},{time:180}], [{id:'exit',time:199,side:'SELL',kind:'Exit',quantity:2},{id:'entry',time:121,side:'BUY',kind:'Entry',quantity:1},{id:'entry2',time:159,side:'BUY',kind:'Entry',quantity:1}]);
 assert.deepEqual(markers.map(m=>m.time),[120,120,180]);
 assert.equal(markers[0].shape,'arrowUp');assert.equal(markers[2].shape,'arrowDown');
});
test('missing minute is never snapped to a different candle',()=>{
 assert.deepEqual(executionMarkers([{time:120},{time:240}],[{time:180,side:'BUY',kind:'Entry',quantity:1}]),[]);
});
