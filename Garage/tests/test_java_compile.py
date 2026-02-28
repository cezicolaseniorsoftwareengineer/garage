"""
Java 17 Compilation Tests — todos os snippets do jogo.

Testa:
  1. node test_all_challenges.js — valida todos os COLA codes com JavaAnalyzer
  2. javac real — compila cada COLA code extraído do game.js com Java 17
  3. Garage AI example codes — compila os exemplos de código profissional
     gerados pela IA (listados em GARAGE_AI_SAMPLES abaixo)

Pré-requisitos (ambos no PATH):
  - Java 17 (javac)
  - Node.js
"""
import os
import sys
import re
import subprocess
import tempfile
import shutil
import json

import pytest

GARAGE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_JS     = os.path.join(GARAGE_DIR, "app", "static", "game.js")
JS_TEST     = os.path.join(GARAGE_DIR, "test_all_challenges.js")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
    )
    return result.returncode, result.stdout, result.stderr


def _javac_available() -> bool:
    try:
        rc, out, _ = _run(["javac", "-version"])
        return rc == 0 or "17" in out or "17" in _
    except FileNotFoundError:
        return False


def _node_available() -> bool:
    try:
        rc, _, _ = _run(["node", "--version"])
        return rc == 0
    except FileNotFoundError:
        return False


JAVAC_SKIP = pytest.mark.skipif(not _javac_available(), reason="javac não encontrado no PATH")
NODE_SKIP  = pytest.mark.skipif(not _node_available(),  reason="node não encontrado no PATH")


def _extract_cola_challenges() -> list[dict]:
    """
    Parse game.js and extract all {id, fileName, cola_code} entries
    from CODE_CHALLENGES[*].helpText.
    """
    with open(GAME_JS, "r", encoding="utf-8") as f:
        source = f.read()

    # Extract each challenge block via regex:
    # id: 'code_XXX', ... fileName: 'XXX.java', ... helpText: '...'
    # Use [\s\S]*? (any char incl newline) instead of [^}]*? to avoid
    # stopping on braces inside Java code.
    pattern = re.compile(
        r"id:\s*'(code_[^']+)'[\s\S]*?fileName:\s*'([^']+)'[\s\S]*?helpText:\s*'((?:[^'\\]|\\.)*)'",
        re.DOTALL,
    )

    results = []
    for m in pattern.finditer(source):
        ch_id    = m.group(1)
        filename = m.group(2)
        help_raw = (
            m.group(3)
            .replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\\\", "\\")
        )

        # Extract COLA block
        cola = _extract_cola(help_raw)
        if cola:
            results.append({
                "id":       ch_id,
                "fileName": filename,
                "cola":     cola,
            })

    return results


def _extract_cola(help_text: str) -> str | None:
    """Extract the copy-paste code block from a helpText string."""
    markers = [
        "COLA -- Copie este código na IDE:\n\n",
        "COLA -- Copie este codigo na IDE:\n\n",
    ]
    for marker in markers:
        idx = help_text.find(marker)
        if idx >= 0:
            return help_text[idx + len(marker):].strip()

    # Fallback: content after "COLA"
    idx = help_text.find("COLA")
    if idx >= 0:
        code_start = help_text.find("\n\n", idx)
        if code_start >= 0:
            return help_text[code_start + 2:].strip()
    return None


def _compile_java(code: str, filename: str, tmp_dir: str) -> tuple[bool, str]:
    """Write code to filename in tmp_dir and compile with javac. Returns (ok, stderr)."""
    java_file = os.path.join(tmp_dir, filename)
    with open(java_file, "w", encoding="utf-8") as f:
        f.write(code)

    rc, _, err = _run(["javac", java_file], cwd=tmp_dir)
    return rc == 0, err


# ---------------------------------------------------------------------------
# Suite 1: node test_all_challenges.js  (JavaAnalyzer + validator)
# ---------------------------------------------------------------------------

class TestNodeJavaAnalyzer:
    """Runs the existing JavaScript regression suite."""

    @NODE_SKIP
    def test_all_challenges_pass_javascript_validator(self):
        """All CODE_CHALLENGES COLA codes must pass JavaAnalyzer + domain validator."""
        if not os.path.exists(JS_TEST):
            pytest.skip("test_all_challenges.js não encontrado")

        rc, stdout, stderr = _run(["node", JS_TEST], cwd=GARAGE_DIR, timeout=60)

        # Print output for debugging on failure
        print("\n--- node test_all_challenges.js stdout ---")
        print(stdout[-3000:] if len(stdout) > 3000 else stdout)
        if stderr:
            print("--- stderr ---")
            print(stderr[-1000:])

        # Must contain "passed" and zero "[FAIL]" lines
        # Note: output may contain "0 FAILED" (word FAILED) which is fine
        assert "[FAIL]" not in stdout, (
            f"Falhas detectadas pelo JavaAnalyzer:\n{stdout}"
        )
        assert "PASSED" in stdout or "PASS" in stdout, (
            f"Resultado inesperado:\n{stdout}"
        )


# ---------------------------------------------------------------------------
# Suite 2: javac real  (Java 17)
# ---------------------------------------------------------------------------

def _cola_test_cases():
    """Generate parametrized test cases for javac compilation."""
    if not os.path.exists(GAME_JS):
        return []
    try:
        return _extract_cola_challenges()
    except Exception:
        return []


_ALL_COLA = _cola_test_cases()


class TestJavacCompilation:
    """Compiles every COLA code from game.js with real javac (Java 17)."""

    @JAVAC_SKIP
    def test_java17_is_available(self):
        rc, out, err = _run(["javac", "-version"])
        version_str = out + err
        assert "17" in version_str, (
            f"Java 17 não encontrado. Versão atual: {version_str.strip()}"
        )

    @JAVAC_SKIP
    @pytest.mark.parametrize(
        "ch",
        _ALL_COLA,
        ids=[c["id"] for c in _ALL_COLA],
    )
    def test_cola_code_compiles_with_javac(self, ch):
        """Each COLA code block must compile successfully with javac."""
        tmp_dir = tempfile.mkdtemp(prefix=f"garage_javac_{ch['id']}_")
        try:
            ok, stderr = _compile_java(ch["cola"], ch["fileName"], tmp_dir)
            assert ok, (
                f"Desafio {ch['id']} ({ch['fileName']}) FALHA na compilação Java 17:\n"
                f"{stderr}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @JAVAC_SKIP
    def test_total_compilable_cola_codes(self):
        """Deve haver pelo menos 20 COLA codes compiláveis no game.js."""
        assert len(_ALL_COLA) >= 20, (
            f"Apenas {len(_ALL_COLA)} COLA codes encontrados no game.js. "
            "Verifique o marcador 'COLA -- Copie este código na IDE:'"
        )


# ---------------------------------------------------------------------------
# Suite 3: Garage AI — exemplos de código profissional
# ---------------------------------------------------------------------------

# Estes são exemplos de código Java profissional que a Garage AI deve ser capaz
# de gerar e que DEVEM compilar com Java 17.  Adicionados aqui como exemplos
# canônicos que a IA retorna no estudo de chat.
GARAGE_AI_SAMPLES = [
    {
        "id": "ai_sample_hello",
        "fileName": "HelloWorld.java",
        "code": """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello World");
    }
}
""",
    },
    {
        "id": "ai_sample_variables",
        "fileName": "Variables.java",
        "code": """
public class Variables {
    public static void main(String[] args) {
        int idade = 20;
        double salario = 3500.50;
        String nome = "Dev";
        boolean ativo = true;
        System.out.println(idade);
        System.out.println(salario);
        System.out.println(nome);
        System.out.println(ativo);
    }
}
""",
    },
    {
        "id": "ai_sample_array",
        "fileName": "ArrayLoop.java",
        "code": """
public class ArrayLoop {
    public static void main(String[] args) {
        int[] nums = {10, 20, 30, 40, 50};
        for (int i = 0; i < nums.length; i++) {
            System.out.println(nums[i]);
        }
    }
}
""",
    },
    {
        "id": "ai_sample_interface",
        "fileName": "ShapeDemo.java",
        "code": """
public class ShapeDemo {
    interface Shape {
        double area();
    }
    static class Circle implements Shape {
        private final double radius;
        Circle(double radius) { this.radius = radius; }
        public double area() { return Math.PI * radius * radius; }
    }
    public static void main(String[] args) {
        Shape s = new Circle(5.0);
        System.out.println("Area: " + s.area());
    }
}
""",
    },
    {
        "id": "ai_sample_generic",
        "fileName": "GenericStack.java",
        "code": """
import java.util.ArrayList;
import java.util.List;

public class GenericStack {
    static class Stack<T> {
        private final List<T> data = new ArrayList<>();
        public void push(T item) { data.add(item); }
        public T pop() {
            if (data.isEmpty()) throw new RuntimeException("Stack vazia");
            return data.remove(data.size() - 1);
        }
        public boolean isEmpty() { return data.isEmpty(); }
    }
    public static void main(String[] args) {
        Stack<Integer> stack = new Stack<>();
        stack.push(1);
        stack.push(2);
        System.out.println(stack.pop()); // 2
        System.out.println(stack.pop()); // 1
    }
}
""",
    },
    {
        "id": "ai_sample_streams",
        "fileName": "StreamDemo.java",
        "code": """
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class StreamDemo {
    public static void main(String[] args) {
        List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        List<Integer> evens = numbers.stream()
            .filter(n -> n % 2 == 0)
            .collect(Collectors.toList());
        System.out.println("Pares: " + evens);
    }
}
""",
    },
    {
        "id": "ai_sample_record",
        "fileName": "RecordDemo.java",
        "code": """
public class RecordDemo {
    record Point(int x, int y) {
        double distanceTo(Point other) {
            int dx = this.x - other.x;
            int dy = this.y - other.y;
            return Math.sqrt(dx * dx + dy * dy);
        }
    }
    public static void main(String[] args) {
        Point a = new Point(0, 0);
        Point b = new Point(3, 4);
        System.out.println("Distancia: " + a.distanceTo(b)); // 5.0
    }
}
""",
    },
    {
        "id": "ai_sample_binary_search",
        "fileName": "BinarySearch.java",
        "code": """
public class BinarySearch {
    static int search(int[] arr, int target) {
        int low = 0, high = arr.length - 1;
        while (low <= high) {
            int mid = low + (high - low) / 2;
            if (arr[mid] == target) return mid;
            if (arr[mid] < target) low = mid + 1;
            else high = mid - 1;
        }
        return -1;
    }
    public static void main(String[] args) {
        int[] arr = {1, 3, 5, 7, 9, 11, 13};
        System.out.println(search(arr, 7));  // 3
        System.out.println(search(arr, 6));  // -1
    }
}
""",
    },
    {
        "id": "ai_sample_hashmap",
        "fileName": "FrequencyMap.java",
        "code": """
import java.util.HashMap;
import java.util.Map;

public class FrequencyMap {
    public static void main(String[] args) {
        String[] words = {"java", "python", "java", "go", "java", "python"};
        Map<String, Integer> freq = new HashMap<>();
        for (String w : words) {
            freq.put(w, freq.getOrDefault(w, 0) + 1);
        }
        freq.forEach((k, v) -> System.out.println(k + ": " + v));
    }
}
""",
    },
    {
        "id": "ai_sample_encapsulation",
        "fileName": "BankAccount.java",
        "code": """
public class BankAccount {
    private final String id;
    private double balance;

    public BankAccount(String id, double initialBalance) {
        if (initialBalance < 0) throw new IllegalArgumentException("Saldo inicial negativo");
        this.id = id;
        this.balance = initialBalance;
    }

    public void deposit(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Valor de deposito invalido");
        this.balance += amount;
    }

    public void withdraw(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Valor de saque invalido");
        if (amount > balance) throw new IllegalStateException("Saldo insuficiente");
        this.balance -= amount;
    }

    public double getBalance() { return balance; }
    public String getId() { return id; }

    public static void main(String[] args) {
        BankAccount acc = new BankAccount("001", 1000.0);
        acc.deposit(500.0);
        acc.withdraw(200.0);
        System.out.println("Saldo: " + acc.getBalance()); // 1300.0
    }
}
""",
    },
    {
        "id": "ai_sample_circuit_breaker",
        "fileName": "CircuitBreaker.java",
        "code": """
public class CircuitBreaker {
    enum State { CLOSED, OPEN, HALF_OPEN }

    private State state = State.CLOSED;
    private int failureCount = 0;
    private final int threshold;
    private long lastFailureTime = 0;
    private final long timeout;

    public CircuitBreaker(int threshold, long timeoutMs) {
        this.threshold = threshold;
        this.timeout = timeoutMs;
    }

    public boolean isAvailable() {
        if (state == State.OPEN) {
            if (System.currentTimeMillis() - lastFailureTime > timeout) {
                state = State.HALF_OPEN;
                return true;
            }
            return false;
        }
        return true;
    }

    public void recordSuccess() {
        failureCount = 0;
        state = State.CLOSED;
    }

    public void recordFailure() {
        failureCount++;
        lastFailureTime = System.currentTimeMillis();
        if (failureCount >= threshold) {
            state = State.OPEN;
        }
    }

    public static void main(String[] args) {
        CircuitBreaker cb = new CircuitBreaker(3, 5000);
        System.out.println("Available: " + cb.isAvailable()); // true
        cb.recordFailure();
        cb.recordFailure();
        cb.recordFailure();
        System.out.println("Available: " + cb.isAvailable()); // false (OPEN)
    }
}
""",
    },
    {
        "id": "ai_sample_plugin_arch",
        "fileName": "PluginDemo.java",
        "code": """
import java.util.ArrayList;
import java.util.List;

public class PluginDemo {
    interface Plugin {
        String name();
        void execute(String input);
    }

    static class PluginRegistry {
        private final List<Plugin> plugins = new ArrayList<>();

        public void register(Plugin plugin) {
            plugins.add(plugin);
        }

        public void runAll(String input) {
            for (Plugin p : plugins) {
                p.execute(input);
            }
        }
    }

    public static void main(String[] args) {
        PluginRegistry registry = new PluginRegistry();
        registry.register(new Plugin() {
            public String name() { return "Logger"; }
            public void execute(String input) {
                System.out.println("[LOG] Input: " + input);
            }
        });
        registry.register(new Plugin() {
            public String name() { return "Validator"; }
            public void execute(String input) {
                System.out.println("[VALID] " + (input != null && !input.isEmpty() ? "OK" : "EMPTY"));
            }
        });
        registry.runAll("Hello Bio Code");
    }
}
""",
    },
]


class TestGarageAISamples:
    """
    Todos os exemplos de código profissional gerados pela Garage AI
    devem compilar com Java 17 sem erros.
    """

    @JAVAC_SKIP
    @pytest.mark.parametrize(
        "sample",
        GARAGE_AI_SAMPLES,
        ids=[s["id"] for s in GARAGE_AI_SAMPLES],
    )
    def test_ai_sample_compiles_with_java17(self, sample):
        tmp_dir = tempfile.mkdtemp(prefix=f"garage_ai_{sample['id']}_")
        try:
            ok, stderr = _compile_java(sample["code"].strip(), sample["fileName"], tmp_dir)
            assert ok, (
                f"Amostra Garage AI '{sample['id']}' FALHOU na compilação Java 17:\n"
                f"{stderr}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @JAVAC_SKIP
    def test_all_ai_samples_count(self):
        assert len(GARAGE_AI_SAMPLES) >= 12, (
            f"Deveria ter ≥12 amostras AI, encontrou {len(GARAGE_AI_SAMPLES)}"
        )
