/**
 * Automated regression test for ALL 24 CODE_CHALLENGES.
 * Extracts the JavaAnalyzer + each challenge's cola code from helpText,
 * runs the cola through the challenge validator, and reports PASS/FAIL.
 *
 * Usage: node test_all_challenges.js
 */

const fs = require('fs');
const path = require('path');

// ---- Load game.js source (normalize CRLF to LF) ----
const gameSource = fs.readFileSync(
    path.join(__dirname, 'app', 'static', 'game.js'),
    'utf-8'
).replace(/\r\n/g, '\n');

// ---- Extract JavaAnalyzer object ----
// Find start/end markers in the source and eval the block.
const analyzerStart = gameSource.indexOf('const JavaAnalyzer = {');
const analyzerEndMarker = '\n};\n\n// ---- IDE coding challenges ----';
const analyzerEnd = gameSource.indexOf(analyzerEndMarker, analyzerStart);
if (analyzerStart < 0 || analyzerEnd < 0) {
    console.error('FATAL: Could not extract JavaAnalyzer from game.js');
    console.error('  analyzerStart=' + analyzerStart + ', analyzerEnd=' + analyzerEnd);
    process.exit(1);
}
const analyzerSource = gameSource.substring(analyzerStart, analyzerEnd + 3); // include '};'
eval(analyzerSource.replace('const JavaAnalyzer', 'var JavaAnalyzer'));

// ---- Extract CODE_CHALLENGES array ----
const challengesStart = gameSource.indexOf('const CODE_CHALLENGES = [');
// Find the closing "];" -- it's followed by SCALE_MISSIONS declaration
const scaleMissionsMarker = '// ---- challenge scale tracks';
const scaleMissionsIdx = gameSource.indexOf(scaleMissionsMarker, challengesStart);
// Search backwards from SCALE_MISSIONS for the "];\n" that closes CODE_CHALLENGES
let challengesEnd = gameSource.lastIndexOf('];\n', scaleMissionsIdx);
if (challengesStart < 0 || challengesEnd < 0 || challengesEnd <= challengesStart) {
    console.error('FATAL: Could not locate CODE_CHALLENGES array');
    console.error('  start=' + challengesStart + ', end=' + challengesEnd + ', scaleMissions=' + scaleMissionsIdx);
    process.exit(1);
}
const challengesSource = gameSource.substring(challengesStart, challengesEnd + 2); // include '];'

// The validators reference JavaAnalyzer, which is already in scope from eval above.
// We also need a minimal State stub for the IDE.open() references, but validators don't use it.
eval(challengesSource.replace('const CODE_CHALLENGES', 'var CODE_CHALLENGES'));

// ---- Extract cola code from helpText ----
function extractCola(helpText) {
    const marker = 'COLA -- Copie este código na IDE:\n\n';
    // Some helpTexts use "codigo" instead of "código"
    const marker2 = 'COLA -- Copie este codigo na IDE:\n\n';
    let idx = helpText.indexOf(marker);
    if (idx >= 0) return helpText.substring(idx + marker.length).trim();
    idx = helpText.indexOf(marker2);
    if (idx >= 0) return helpText.substring(idx + marker2.length).trim();
    // Fallback: try to find code after "COLA"
    idx = helpText.indexOf('COLA');
    if (idx >= 0) {
        const codeStart = helpText.indexOf('\n\n', idx);
        if (codeStart >= 0) return helpText.substring(codeStart + 2).trim();
    }
    return null;
}

// ---- Run all tests ----
console.log('='.repeat(70));
console.log('  REGRESSION TEST: JavaAnalyzer vs ALL 24 CODE_CHALLENGES cola codes');
console.log('='.repeat(70));
console.log();

let passed = 0;
let failed = 0;
const failures = [];

for (const ch of CODE_CHALLENGES) {
    const cola = extractCola(ch.helpText);
    if (!cola) {
        console.log(`[SKIP] ${ch.id} -- cola code not found in helpText`);
        continue;
    }

    // Test 1: JavaAnalyzer.analyze() on raw cola code
    const analyzeResult = JavaAnalyzer.analyze(cola);

    // Test 2: Full validator (includes analyze + domain checks)
    let validatorResult;
    try {
        validatorResult = ch.validator(cola);
    } catch (err) {
        validatorResult = { ok: false, msg: 'EXCEPTION: ' + err.message };
    }

    const analyzerOk = analyzeResult.ok;
    const validatorOk = validatorResult.ok;

    if (analyzerOk && validatorOk) {
        console.log(`[PASS] ${ch.id} (${ch.stage} / ${ch.region})`);
        passed++;
    } else {
        console.log(`[FAIL] ${ch.id} (${ch.stage} / ${ch.region})`);
        if (!analyzerOk) {
            console.log(`       Analyzer: ${analyzeResult.msg}`);
        }
        if (!validatorOk) {
            console.log(`       Validator: ${validatorResult.msg}`);
        }
        failed++;
        failures.push({
            id: ch.id,
            stage: ch.stage,
            region: ch.region,
            analyzerMsg: analyzerOk ? null : analyzeResult.msg,
            validatorMsg: validatorOk ? null : validatorResult.msg,
            cola: cola,
        });
    }
}

console.log();
console.log('='.repeat(70));
console.log(`  RESULT: ${passed} PASSED, ${failed} FAILED out of ${CODE_CHALLENGES.length}`);
console.log('='.repeat(70));

if (failures.length > 0) {
    console.log();
    console.log('FAILURE DETAILS:');
    console.log('-'.repeat(70));
    for (const f of failures) {
        console.log(`\n>> ${f.id} (${f.stage} / ${f.region})`);
        if (f.analyzerMsg) console.log(`   ANALYZER ERROR: ${f.analyzerMsg}`);
        if (f.validatorMsg) console.log(`   VALIDATOR ERROR: ${f.validatorMsg}`);
        console.log(`   COLA CODE:\n${f.cola.split('\n').map(l => '   | ' + l).join('\n')}`);
    }
}

// ---- Phase 2: Starter code crash test ----
console.log();
console.log('='.repeat(70));
console.log('  CRASH TEST: JavaAnalyzer.analyze() on starterCode (must not throw)');
console.log('='.repeat(70));
console.log();

let starterCrashes = 0;
for (const ch of CODE_CHALLENGES) {
    try {
        JavaAnalyzer.analyze(ch.starterCode || '');
        console.log(`[SAFE] ${ch.id} starterCode`);
    } catch (err) {
        console.log(`[CRASH] ${ch.id} starterCode -- ${err.message}`);
        starterCrashes++;
    }
}

// ---- Phase 3: Edge case regression tests ----
console.log();
console.log('='.repeat(70));
console.log('  EDGE CASE REGRESSION TESTS');
console.log('='.repeat(70));
console.log();

const edgeCases = [
    {
        name: 'String.length() vs array.length (PR b20165c)',
        code: `public class Test {
    static boolean isAnagram(String s, String t) {
        if (s.length() != t.length()) return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(isAnagram("a", "b"));
    }
}`,
        expectOk: true
    },
    {
        name: 'new int[]{} in println (PR 5a23644)',
        code: `import java.util.HashSet;
public class Test {
    static boolean check(int[] nums) { return true; }
    public static void main(String[] args) {
        System.out.println(check(new int[]{1, 2, 3}));
    }
}`,
        expectOk: true
    },
    {
        name: 'Block comment in code (PR 6c75f18)',
        code: `import java.util.LinkedList;
/* This is a block comment
   spanning multiple lines */
public class Test {
    public static void main(String[] args) {
        LinkedList<String> list = new LinkedList<>();
        list.add("Alpha");
        System.out.println(list);
    }
}`,
        expectOk: true
    },
    {
        name: '@Override annotation (PR 6c75f18)',
        code: `interface Animal {
    String speak();
}
class Dog implements Animal {
    @Override
    public String speak() {
        return "Woof";
    }
}
public class Test {
    public static void main(String[] args) {
        Animal a = new Dog();
        System.out.println(a.speak());
    }
}`,
        expectOk: true
    },
    {
        name: 'Nested generics Map<Integer, List<Integer>> (new)',
        code: `import java.util.*;
public class Test {
    public static void main(String[] args) {
        Map<Integer, List<Integer>> graph = new HashMap<>();
        graph.put(0, Arrays.asList(1, 2));
        System.out.println(graph);
    }
}`,
        expectOk: true
    },
    {
        name: 'Escaped quotes inside strings',
        code: `public class Test {
    public static void main(String[] args) {
        String s = "She said \\"hello\\"";
        System.out.println(s);
    }
}`,
        expectOk: true
    },
    {
        name: 'Nested println with method call',
        code: `import java.util.Arrays;
public class Test {
    static int[] solve(int[] a) { return a; }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(solve(new int[]{1,2,3})));
    }
}`,
        expectOk: true
    },
    {
        name: 'PriorityQueue with Comparable',
        code: `import java.util.PriorityQueue;
public class Test {
    static class Task implements Comparable<Task> {
        String name;
        int priority;
        Task(String n, int p) { name = n; priority = p; }
        @Override
        public int compareTo(Task other) {
            return Integer.compare(this.priority, other.priority);
        }
    }
    public static void main(String[] args) {
        PriorityQueue<Task> pq = new PriorityQueue<>();
        pq.add(new Task("Deploy", 1));
        Task t = pq.poll();
        System.out.println(t.name);
    }
}`,
        expectOk: true
    },
    {
        name: 'for-each with nested generic',
        code: `import java.util.*;
public class Test {
    public static void main(String[] args) {
        Map<String, Integer> map = new HashMap<>();
        map.put("a", 1);
        for (Map.Entry<String, Integer> e : map.entrySet()) {
            System.out.println(e.getKey() + "=" + e.getValue());
        }
    }
}`,
        expectOk: true
    },
    {
        name: 'while loop with no braces (Allman)',
        code: `public class Test {
    public static void main(String[] args) {
        int i = 0;
        while (i < 5)
        {
            System.out.println(i);
            i++;
        }
    }
}`,
        expectOk: true
    },
];

let edgePassed = 0;
let edgeFailed = 0;
for (const tc of edgeCases) {
    const result = JavaAnalyzer.analyze(tc.code);
    const ok = result.ok === tc.expectOk;
    if (ok) {
        console.log(`[PASS] ${tc.name}`);
        edgePassed++;
    } else {
        console.log(`[FAIL] ${tc.name}`);
        console.log(`       Expected ok=${tc.expectOk}, got ok=${result.ok}`);
        if (result.msg) console.log(`       Msg: ${result.msg}`);
        edgeFailed++;
    }
}

// ---- Final summary ----
console.log();
console.log('='.repeat(70));
console.log(`  SUMMARY`);
console.log(`  Cola codes:    ${passed}/${CODE_CHALLENGES.length} passed`);
console.log(`  Starter crash: ${starterCrashes} crashes`);
console.log(`  Edge cases:    ${edgePassed}/${edgeCases.length} passed`);
console.log('='.repeat(70));

const totalFail = failures.length + starterCrashes + edgeFailed;
if (totalFail > 0) {
    console.log(`\n${totalFail} TOTAL FAILURE(S). Fix required.`);
    process.exit(1);
} else {
    console.log('\nALL TESTS GREEN. System verified.');
    process.exit(0);
}
