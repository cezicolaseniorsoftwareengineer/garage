/* jshint esversion:6 */
var fs   = require('fs');
var path = require('path');

var gamePath = path.join(__dirname, 'app', 'static', 'game.js');
if (!fs.existsSync(gamePath)) { console.error('FATAL: game.js not found'); process.exit(1); }
var src = fs.readFileSync(gamePath, 'utf-8').replace(/\r\n/g, '\n');

// --- extract JavaAnalyzer (assign to outer var to escape IIFE scope) ---
var JavaAnalyzer;
(function () {
    var s = src.indexOf('const JavaAnalyzer = {');
    var eMk = '\n};\n\n// ---- IDE coding challenges ----';
    var e = src.indexOf(eMk, s);
    if (s < 0 || e < 0) { console.error('FATAL: JavaAnalyzer not found s=' + s + ' e=' + e); process.exit(1); }
    eval('JavaAnalyzer = ' + src.substring(s + 'const JavaAnalyzer ='.length, e + 3));
})();

// --- extract CODE_CHALLENGES ---
var CODE_CHALLENGES;
(function () {
    var s = src.indexOf('const CODE_CHALLENGES = [');
    var mk = '// ---- challenge scale tracks (Apple/Nubank) ----';
    var mi = src.indexOf(mk, s);
    var e = src.lastIndexOf('];\n', mi);
    if (s < 0 || e < 0 || mi < 0) { console.error('FATAL: CODE_CHALLENGES not found s=' + s + ' e=' + e + ' mi=' + mi); process.exit(1); }
    eval('CODE_CHALLENGES = ' + src.substring(s + 'const CODE_CHALLENGES ='.length, e + 2));
})();

// --- extract SCALE_MISSIONS ---
var SCALE_MISSIONS;
(function () {
    var s = src.indexOf('const SCALE_MISSIONS = {');
    var mk = '\n// ---- IDE controller ----';
    var mi = src.indexOf(mk, s);
    var e = src.lastIndexOf('};\n', mi);
    if (s < 0 || e < 0 || e <= s) { console.error('FATAL: SCALE_MISSIONS not found s=' + s + ' e=' + e + ' mi=' + mi); process.exit(1); }
    eval('SCALE_MISSIONS = ' + src.substring(s + 'const SCALE_MISSIONS ='.length, e + 3));
})();

function extractCola(h) {
    if (!h) return null;
    var i = h.indexOf('COLA --');
    if (i < 0) return null;
    var b = h.indexOf('\n\n', i);
    if (b < 0) return null;
    return h.substring(b + 2).trim();
}

function runValidator(fn, code) {
    try { return fn(code); }
    catch (e) { return { ok: false, msg: 'EXCEPTION: ' + e.message }; }
}

var passed = 0, failed = 0, failures = [];
var HR = '='.repeat(76), hr = '-'.repeat(76);

console.log('\n' + HR);
console.log('  404 GARAGE -- FULL CHALLENGE BATTERY TEST');
console.log(HR + '\n');

// === SECTION 1: Plain challenges ===
console.log('[ PLAIN CHALLENGES: ' + CODE_CHALLENGES.length + ' total ]\n' + hr);
CODE_CHALLENGES.forEach(function(ch) {
    var cola = extractCola(ch.helpText);
    if (!cola) { console.log('  [SKIP] ' + ch.id + ' -- no COLA'); return; }
    var aR = JavaAnalyzer.analyze(cola);
    var vR = runValidator(ch.validator.bind(ch), cola);
    if (aR.ok && vR.ok) {
        console.log('  [PASS] ' + ch.id.padEnd(26) + (ch.stage || '') + ' / ' + (ch.region || ''));
        passed++;
    } else {
        console.log('  [FAIL] ' + ch.id.padEnd(26) + (ch.stage || '') + ' / ' + (ch.region || ''));
        if (!aR.ok) console.log('         ANALYZER : ' + aR.msg);
        if (!vR.ok) console.log('         VALIDATOR: ' + vR.msg);
        failed++;
        failures.push({ sec:'PLAIN', label:ch.id, aMsg:aR.ok?null:aR.msg, vMsg:vR.ok?null:vR.msg, cola:cola });
    }
});

// === SECTION 2: Scale missions ===
console.log('\n[ SCALE MISSIONS: step COLAs must pass BOTH main + step validator ]\n' + hr);
var chMap = {};
CODE_CHALLENGES.forEach(function(c) { chMap[c.id] = c; });

Object.keys(SCALE_MISSIONS).forEach(function(mId) {
    var mission = SCALE_MISSIONS[mId];
    var mc = chMap[mId];
    if (!mc) { console.log('  [SKIP] ' + mId + ' -- not in CODE_CHALLENGES'); return; }
    mission.steps.forEach(function(step, si) {
        var lbl = (mId + ' step' + (si + 1) + '/' + mission.steps.length).padEnd(38);
        if (!step.validator) {
            var bc = extractCola(mc.helpText);
            if (!bc) { console.log('  [SKIP] ' + lbl + ' -- no base COLA'); return; }
            var baR = JavaAnalyzer.analyze(bc);
            var bvR = runValidator(mc.validator.bind(mc), bc);
            if (baR.ok && bvR.ok) { console.log('  [PASS] ' + lbl + ' (base)'); passed++; }
            else {
                console.log('  [FAIL] ' + lbl + ' (base)');
                if (!baR.ok) console.log('         ANALYZER : ' + baR.msg);
                if (!bvR.ok) console.log('         VALIDATOR: ' + bvR.msg);
                failed++;
                failures.push({ sec:'SCALE_BASE', label:lbl.trim(), aMsg:baR.ok?null:baR.msg, vMsg:bvR.ok?null:bvR.msg, cola:bc });
            }
            return;
        }
        var sc = extractCola(step.helpText);
        if (!sc) { console.log('  [SKIP] ' + lbl + ' -- no COLA in step'); return; }
        var mR = runValidator(mc.validator.bind(mc), sc);
        var sR = runValidator(step.validator.bind(step), sc);
        if (mR.ok && sR.ok) {
            console.log('  [PASS] ' + lbl + ' main:ok step:ok');
            passed++;
        } else {
            console.log('  [FAIL] ' + lbl + ' main:' + (mR.ok ? 'ok' : 'FAIL') + ' step:' + (sR.ok ? 'ok' : 'FAIL'));
            if (!mR.ok) console.log('         MAIN VALIDATOR: ' + mR.msg);
            if (!sR.ok) console.log('         STEP VALIDATOR: ' + sR.msg);
            failed++;
            failures.push({ sec:'SCALE', label:lbl.trim(), mMsg:mR.ok?null:mR.msg, sMsg:sR.ok?null:sR.msg, cola:sc });
        }
    });
});

// === SECTION 3: Starter code safety ===
console.log('\n[ STARTER CODE SAFETY ]\n' + hr);
var crashes = 0;
CODE_CHALLENGES.forEach(function(c) {
    try { JavaAnalyzer.analyze(c.starterCode || ''); }
    catch (e) { console.log('  [CRASH] ' + c.id + ' -- ' + e.message); crashes++; }
});
if (!crashes) console.log('  All ' + CODE_CHALLENGES.length + ' starter codes safe');

// === SUMMARY ===
console.log('\n' + HR);
console.log('  RESULT: ' + passed + ' PASSED  |  ' + failed + ' FAILED  |  ' + crashes + ' CRASHES');
console.log(HR);

if (failures.length > 0) {
    console.log('\nFAILURE DETAILS:\n' + hr);
    failures.forEach(function(f) {
        console.log('\n>> [' + f.sec + '] ' + f.label);
        if (f.aMsg) console.log('   ANALYZER  : ' + f.aMsg);
        if (f.vMsg) console.log('   VALIDATOR : ' + f.vMsg);
        if (f.mMsg) console.log('   MAIN VAL  : ' + f.mMsg);
        if (f.sMsg) console.log('   STEP VAL  : ' + f.sMsg);
        console.log('   COLA (first 10 lines):');
        f.cola.split('\n').slice(0, 10).forEach(function(l) { console.log('   | ' + l); });
    });
}

var tot = failed + crashes;
if (tot > 0) { console.log('\n' + tot + ' failure(s). Fix required.\n'); process.exit(1); }
else { console.log('\nALL TESTS GREEN.\n'); process.exit(0); }
