// Drive the REAL configurator outputMapping.js with synthetic MSP data and
// print the output table. Used by compare_js_c.py to diff JS vs C behavior.
//
// Usage: node drive.js <json-file>
//   json-file: {"entries":[{"timerId":n,"usageFlags":u32,"specialLabels":n}...],
//               "motors":N,"servos":["S1",...],"isMR":bool}
// Prints one JSON line: {"outputTable":[...], "outputCount":N}
import { readFileSync } from 'fs';
import OutputMappingCollection from '../../../../../inav-configurator/js/outputMapping.js';

const input = JSON.parse(readFileSync(process.argv[2], 'utf8'));

const om = new OutputMappingCollection();
for (const e of input.entries) {
    om.put({ timerId: e.timerId, usageFlags: e.usageFlags, specialLabels: e.specialLabels || 0 });
}
const outputTable = om.getOutputTable(input.isMR, input.motors, input.servos);
console.log(JSON.stringify({ outputTable, outputCount: om.getOutputCount() }));
