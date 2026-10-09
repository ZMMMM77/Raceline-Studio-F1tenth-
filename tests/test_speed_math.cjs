const assert = require('node:assert/strict');
const {scaleSpeeds} = require('../raceline_studio/static/speed_math.js');
const input = [6,5,5.0000001,5,5.1,5,8,7];
const selection = [1,2,3,4,5];
let result = scaleSpeeds(input, selection, 1.5, 5, 10);
for (const i of selection) assert.equal(result[i],input[i]*1.5);
assert.equal(result[0],6);assert.equal(result[6],8);assert.equal(result[7],7);
assert.equal(input[1],5); // Immutable source for undo.
result=scaleSpeeds(result,selection,1.5,5,10);
for(const i of selection)assert.equal(result[i],10); // No alternating floor-speed points.
assert.deepEqual(scaleSpeeds([5,8,10],[0,1,2],.95,5,10),[5,7.6,9.5]);
assert.deepEqual(scaleSpeeds([5,6],[0,0],1.5,5,10),[7.5,6]);
assert.deepEqual(scaleSpeeds([5,5],[0,1],1.5,5,5),[5,5]);
assert.deepEqual(scaleSpeeds(input,[],1.5,5,10),input);
assert.throws(()=>scaleSpeeds(input,[100],1.5,5,10));
const ratio=result.map(v=>(v-5)/5);
assert.deepEqual(ratio.map(r=>5+r*5),result);
console.log('Speed multiplier regression checks passed: floor speeds, contiguous selection, repeated clicks, caps, unselected points, undo source, export ratios.');
