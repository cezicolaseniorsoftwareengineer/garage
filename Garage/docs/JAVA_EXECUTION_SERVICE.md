# Base Técnica: Java 17 + Spring Boot — Execution Service
## 404 Garage · Bio Code Technology Ltda
**Status:** Aprovado para Implementação
**Versão:** 1.0
**Data:** 27/02/2026
**Autor:** CeziCola · Senior Software Engineer

---

## 1. Motivação e Problema

O jogo atualmente usa **apenas múltipla escolha (MCQ)** para ensinar Java. Isso cria um gap pedagógico crítico:

| Situação Atual | Situação Após Integração |
|----------------|--------------------------|
| Jogador lê código Java | Jogador **escreve** código Java |
| Quiz sobre invariantes | Escreve construtor que **valida** invariante |
| Teoria sobre BFS | **Implementa** BFS no grafo social |
| Explicação de Circuit Breaker | **Codifica** com Spring Retry |
| Score por resposta correta | Score por **testes JUnit passando** |

**A integração transforma o 404 Garage de quiz sobre engenharia em plataforma de engenharia real.**

---

## 2. Arquitetura da Solução

```
┌──────────────────────────────────────────────────────────────────────┐
│                         404 Garage Platform                          │
│                                                                      │
│  ┌─────────────────┐   HTTP/JSON   ┌─────────────────────────────┐  │
│  │  Frontend        │──────────────▶│  FastAPI (Python 3.13)      │  │
│  │  HTML5 Canvas    │◀─────────────│  Auth · Game Logic           │  │
│  │  Monaco Editor   │              │  Progress · Leaderboard      │  │
│  └─────────────────┘              └──────────┬──────────────────── │  │
│                                             │ HTTP interno          │  │
│                                             ▼                       │  │
│                                  ┌─────────────────────────────┐   │  │
│                                  │  Spring Boot (Java 17)       │   │  │
│                                  │  Code Execution Service      │   │  │
│                                  │  POST /execute               │   │  │
│                                  │  Sandbox · JUnit runner      │   │  │
│                                  └─────────────────────────────┘   │  │
└──────────────────────────────────────────────────────────────────────┘
```

**Regra de separação de responsabilidades:**
- **FastAPI** → orquestra tudo: auth, progresso, leaderboard, pontuação final
- **Spring Boot** → executa UMA coisa: compila e roda o código Java do jogador
- **Frontend** → Monaco Editor para edição de código in-browser

---

## 3. Estrutura de Diretórios do Novo Serviço

Criar dentro do repo existente:

```
Garage_Game/
├── Garage/                         # Python FastAPI (existente)
│   └── ...
└── execution-service/              # NOVO — Java 17 + Spring Boot
    ├── pom.xml
    ├── Dockerfile
    ├── .env.example
    └── src/
        ├── main/
        │   ├── java/
        │   │   └── com/garage/execution/
        │   │       ├── ExecutionServiceApplication.java   # main()
        │   │       ├── config/
        │   │       │   ├── SandboxConfig.java             # limites de segurança
        │   │       │   └── WebConfig.java                 # CORS
        │   │       ├── controller/
        │   │       │   └── ExecutionController.java       # POST /execute
        │   │       ├── service/
        │   │       │   ├── ExecutionService.java          # orquestra
        │   │       │   ├── JavaCompilerService.java       # javax.tools
        │   │       │   └── TestRunnerService.java         # JUnit 5 launcher
        │   │       ├── domain/
        │   │       │   ├── ExecutionRequest.java          # Record (input)
        │   │       │   ├── ExecutionResult.java           # Record (output)
        │   │       │   └── TestSuite.java                 # testes por challenge
        │   │       └── repository/
        │   │           └── ChallengeTestRegistry.java     # mapa challengeId → testes
        │   └── resources/
        │       ├── application.yml
        │       └── test-suites/                           # testes JUnit por desafio
        │           ├── intern_01_xerox_object_creation.java
        │           ├── intern_02_xerox_naming.java
        │           └── ...
        └── test/
            └── java/
                └── com/garage/execution/
                    ├── ExecutionControllerTest.java
                    └── JavaCompilerServiceTest.java
```

---

## 4. Contratos de API

### 4.1 Request — `POST /execute`

```json
{
  "challenge_id": "intern_01_xerox_object_creation",
  "player_code": "public class Account {\n    private final String id;\n    private final java.math.BigDecimal balance;\n\n    public Account(String id, java.math.BigDecimal initialBalance) {\n        if (id == null || id.isBlank()) throw new IllegalArgumentException(\"id cannot be blank\");\n        if (initialBalance == null || initialBalance.compareTo(java.math.BigDecimal.ZERO) < 0)\n            throw new IllegalArgumentException(\"balance cannot be negative\");\n        this.id = id;\n        this.balance = initialBalance;\n    }\n\n    public String getId() { return id; }\n    public java.math.BigDecimal getBalance() { return balance; }\n}",
  "language": "java17"
}
```

### 4.2 Response — Sucesso

```json
{
  "challenge_id": "intern_01_xerox_object_creation",
  "compiled": true,
  "compile_errors": [],
  "tests_total": 4,
  "tests_passed": 4,
  "tests_failed": 0,
  "failures": [],
  "score_percent": 100,
  "execution_time_ms": 312,
  "feedback": "Perfeito! O objeto nasce válido e rejeita estado inválido no construtor."
}
```

### 4.3 Response — Falha de compilação

```json
{
  "challenge_id": "intern_01_xerox_object_creation",
  "compiled": false,
  "compile_errors": [
    "Account.java:5: error: ';' expected\n    public Account(String id BigDecimal balance) {\n                              ^\n1 error"
  ],
  "tests_total": 0,
  "tests_passed": 0,
  "tests_failed": 0,
  "failures": [],
  "score_percent": 0,
  "execution_time_ms": 45,
  "feedback": "Erro de compilação. Verifique a sintaxe na linha 5."
}
```

### 4.4 Response — Testes falhando

```json
{
  "challenge_id": "intern_01_xerox_object_creation",
  "compiled": true,
  "compile_errors": [],
  "tests_total": 4,
  "tests_passed": 2,
  "tests_failed": 2,
  "failures": [
    "test_null_id_throws: expected IllegalArgumentException but no exception was thrown",
    "test_negative_balance_throws: expected IllegalArgumentException but no exception was thrown"
  ],
  "score_percent": 50,
  "execution_time_ms": 187,
  "feedback": "A construção aceita valores inválidos. Adicione validação no construtor."
}
```

---

## 5. Código de Implementação Completo

### 5.1 `pom.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.3</version>
        <relativePath/>
    </parent>

    <groupId>com.garage</groupId>
    <artifactId>execution-service</artifactId>
    <version>1.0.0</version>
    <name>404 Garage — Java Execution Service</name>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Web (embedded Tomcat) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Actuator — health check para o FastAPI monitorar -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Jackson — JSON serialization -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>

        <!-- JUnit 5 Launcher — para rodar testes programaticamente -->
        <dependency>
            <groupId>org.junit.platform</groupId>
            <artifactId>junit-platform-launcher</artifactId>
            <scope>compile</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <scope>compile</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <scope>compile</scope>
        </dependency>

        <!-- Tests do próprio serviço -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

---

### 5.2 `application.yml`

```yaml
server:
  port: 8080

spring:
  application:
    name: garage-execution-service

# Configurações de segurança do sandbox
garage:
  sandbox:
    timeout-ms: 5000          # timeout por execução
    max-output-bytes: 10240   # 10 KB máximo de output
    allowed-packages:         # whitelist de imports permitidos
      - java.util
      - java.util.stream
      - java.math
      - java.time
      - java.util.concurrent
      - java.util.function
    forbidden-packages:       # blacklist — jamais permitir
      - java.io.File
      - java.net
      - java.lang.reflect
      - java.lang.Runtime
      - java.lang.ProcessBuilder
      - sun.misc

management:
  endpoints:
    web:
      exposure:
        include: health,info
  endpoint:
    health:
      show-details: never
```

---

### 5.3 `ExecutionServiceApplication.java`

```java
package com.garage.execution;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ExecutionServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ExecutionServiceApplication.class, args);
    }
}
```

---

### 5.4 `domain/ExecutionRequest.java` (Java 17 Record)

```java
package com.garage.execution.domain;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

/**
 * Immutable input for a code execution request.
 * Uses Java 17 Records — zero boilerplate, built-in equals/hashCode/toString.
 */
public record ExecutionRequest(
    @NotBlank String challengeId,
    @NotBlank String playerCode,
    @Pattern(regexp = "java17") String language
) {}
```

---

### 5.5 `domain/ExecutionResult.java` (Java 17 Record)

```java
package com.garage.execution.domain;

import java.util.List;

/**
 * Immutable output from a code execution.
 */
public record ExecutionResult(
    String challengeId,
    boolean compiled,
    List<String> compileErrors,
    int testsTotal,
    int testsPassed,
    int testsFailed,
    List<String> failures,
    int scorePercent,
    long executionTimeMs,
    String feedback
) {
    /** Atalho para resultado de falha de compilação. */
    public static ExecutionResult compilationFailure(
        String challengeId,
        List<String> errors,
        long timeMs
    ) {
        return new ExecutionResult(
            challengeId, false, errors,
            0, 0, 0, List.of(),
            0, timeMs,
            "Erro de compilação. Corrija e tente novamente."
        );
    }

    /** Atalho para timeout. */
    public static ExecutionResult timeout(String challengeId) {
        return new ExecutionResult(
            challengeId, true, List.of(),
            0, 0, 0, List.of("Execution timed out after 5000ms"),
            0, 5000L,
            "Sua solução entrou em loop infinito ou excedeu o tempo limite."
        );
    }
}
```

---

### 5.6 `service/JavaCompilerService.java`

```java
package com.garage.execution.service;

import org.springframework.stereotype.Service;

import javax.tools.*;
import java.io.*;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;

/**
 * Compiles player-submitted Java code entirely in-memory using javax.tools (JDK built-in).
 * No temp files. No disk I/O.
 */
@Service
public class JavaCompilerService {

    private final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();

    public record CompilationResult(boolean success, List<String> errors, byte[] classBytes) {}

    public CompilationResult compile(String className, String sourceCode) {
        if (compiler == null) {
            return new CompilationResult(false,
                List.of("JavaCompiler not available. Ensure JDK (not JRE) is used."),
                null);
        }

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        InMemoryFileManager fileManager = new InMemoryFileManager(
            compiler.getStandardFileManager(diagnostics, null, null)
        );

        JavaFileObject source = new StringJavaSource(className, sourceCode);
        JavaCompiler.CompilationTask task = compiler.getTask(
            null, fileManager, diagnostics, null, null, List.of(source)
        );

        boolean success = task.call();

        if (!success) {
            List<String> errors = diagnostics.getDiagnostics().stream()
                .filter(d -> d.getKind() == Diagnostic.Kind.ERROR)
                .map(d -> d.toString())
                .toList();
            return new CompilationResult(false, errors, null);
        }

        byte[] classBytes = fileManager.getClassBytes(className);
        return new CompilationResult(true, List.of(), classBytes);
    }

    // --- Inner classes for in-memory compilation ---

    static class StringJavaSource extends SimpleJavaFileObject {
        private final String code;

        StringJavaSource(String name, String code) {
            super(URI.create("string:///" + name + Kind.SOURCE.extension), Kind.SOURCE);
            this.code = code;
        }

        @Override
        public CharSequence getCharContent(boolean ignoreEncodingErrors) {
            return code;
        }
    }

    static class InMemoryFileManager extends ForwardingJavaFileManager<StandardJavaFileManager> {
        private final java.util.Map<String, byte[]> classMap = new java.util.HashMap<>();

        InMemoryFileManager(StandardJavaFileManager sfm) {
            super(sfm);
        }

        @Override
        public JavaFileObject getJavaFileForOutput(
            Location location, String className,
            JavaFileObject.Kind kind, FileObject sibling) {
            return new SimpleJavaFileObject(
                URI.create("mem:///" + className + kind.extension), kind) {
                @Override
                public OutputStream openOutputStream() {
                    return new ByteArrayOutputStream() {
                        @Override
                        public void close() throws IOException {
                            super.close();
                            classMap.put(className, toByteArray());
                        }
                    };
                }
            };
        }

        byte[] getClassBytes(String className) {
            return classMap.get(className);
        }
    }
}
```

---

### 5.7 `service/TestRunnerService.java`

```java
package com.garage.execution.service;

import com.garage.execution.domain.ExecutionResult;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * Loads compiled player bytes as a ClassLoader, then runs the associated
 * JUnit 5 test suite for the challenge programmatically.
 */
@Service
public class TestRunnerService {

    public record RunResult(int total, int passed, int failed, List<String> failures) {}

    public RunResult run(String challengeId, byte[] playerClassBytes, String className) {
        // Inject player class into isolated ClassLoader
        ByteArrayClassLoader classLoader = new ByteArrayClassLoader(
            className, playerClassBytes, Thread.currentThread().getContextClassLoader()
        );

        // Load the test suite registered for this challenge
        String testClassName = "com.garage.execution.suites." + toCamelCase(challengeId) + "Test";
        Class<?> testClass;
        try {
            testClass = classLoader.loadClass(testClassName);
        } catch (ClassNotFoundException e) {
            return new RunResult(0, 0, 0, List.of("Test suite not found for: " + challengeId));
        }

        SummaryGeneratingListener listener = new SummaryGeneratingListener();
        LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
            .selectors(DiscoverySelectors.selectClass(testClass))
            .build();

        Launcher launcher = LauncherFactory.create();
        launcher.discover(request);
        launcher.execute(request, listener);

        var summary = listener.getSummary();
        long total   = summary.getTestsStartedCount();
        long passed  = summary.getTestsSucceededCount();
        long failed  = summary.getTestsFailedCount();

        List<String> failures = summary.getFailures().stream()
            .map(f -> f.getTestIdentifier().getDisplayName() + ": " + f.getException().getMessage())
            .toList();

        return new RunResult((int) total, (int) passed, (int) failed, failures);
    }

    private static String toCamelCase(String challengeId) {
        // "intern_01_xerox_object_creation" → "Intern01XeroxObjectCreation"
        String[] parts = challengeId.split("_");
        StringBuilder sb = new StringBuilder();
        for (String part : parts) {
            if (!part.isEmpty()) {
                sb.append(Character.toUpperCase(part.charAt(0)));
                sb.append(part.substring(1).toLowerCase());
            }
        }
        return sb.toString();
    }

    // Isolated ClassLoader — garante que código do jogador não vaza
    static class ByteArrayClassLoader extends ClassLoader {
        private final String targetName;
        private final byte[] bytes;

        ByteArrayClassLoader(String targetName, byte[] bytes, ClassLoader parent) {
            super(parent);
            this.targetName = targetName;
            this.bytes = bytes;
        }

        @Override
        protected Class<?> findClass(String name) throws ClassNotFoundException {
            if (name.equals(targetName)) {
                return defineClass(name, bytes, 0, bytes.length);
            }
            return super.findClass(name);
        }
    }
}
```

---

### 5.8 `service/ExecutionService.java`

```java
package com.garage.execution.service;

import com.garage.execution.config.SandboxConfig;
import com.garage.execution.domain.ExecutionRequest;
import com.garage.execution.domain.ExecutionResult;
import com.garage.execution.service.JavaCompilerService.CompilationResult;
import com.garage.execution.service.TestRunnerService.RunResult;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.*;

@Service
public class ExecutionService {

    private final JavaCompilerService compilerService;
    private final TestRunnerService testRunnerService;
    private final SandboxConfig sandboxConfig;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor(); // Java 21+, ou newCachedThreadPool() no Java 17

    public ExecutionService(
        JavaCompilerService compilerService,
        TestRunnerService testRunnerService,
        SandboxConfig sandboxConfig
    ) {
        this.compilerService = compilerService;
        this.testRunnerService = testRunnerService;
        this.sandboxConfig = sandboxConfig;
    }

    public ExecutionResult execute(ExecutionRequest request) {
        long start = System.currentTimeMillis();
        String className = extractClassName(request.playerCode());

        // 1. Compilar
        CompilationResult compiled = compilerService.compile(className, request.playerCode());
        if (!compiled.success()) {
            return ExecutionResult.compilationFailure(
                request.challengeId(),
                compiled.errors(),
                System.currentTimeMillis() - start
            );
        }

        // 2. Executar testes com timeout via Future
        Future<RunResult> future = executor.submit(() ->
            testRunnerService.run(request.challengeId(), compiled.classBytes(), className)
        );

        RunResult run;
        try {
            run = future.get(sandboxConfig.getTimeoutMs(), TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            future.cancel(true);
            return ExecutionResult.timeout(request.challengeId());
        } catch (Exception e) {
            return new ExecutionResult(
                request.challengeId(), true, List.of(),
                0, 0, 0, List.of("Internal error: " + e.getMessage()),
                0, System.currentTimeMillis() - start,
                "Erro interno ao executar testes."
            );
        }

        int scorePercent = run.total() > 0
            ? (run.passed() * 100) / run.total()
            : 0;

        String feedback = buildFeedback(run.passed(), run.total(), request.challengeId());

        return new ExecutionResult(
            request.challengeId(),
            true,
            List.of(),
            run.total(),
            run.passed(),
            run.failed(),
            run.failures(),
            scorePercent,
            System.currentTimeMillis() - start,
            feedback
        );
    }

    /** Extrai o nome da classe pública do código submetido. */
    private String extractClassName(String code) {
        java.util.regex.Matcher m =
            java.util.regex.Pattern.compile("public\\s+(?:class|interface|enum|record)\\s+(\\w+)")
                .matcher(code);
        return m.find() ? m.group(1) : "Solution";
    }

    private String buildFeedback(int passed, int total, String challengeId) {
        if (passed == total && total > 0) return "Perfeito! Todos os testes passaram.";
        if (passed == 0)                  return "Nenhum teste passou. Revise sua lógica.";
        return passed + "/" + total + " testes passaram. Continue ajustando.";
    }
}
```

---

### 5.9 `controller/ExecutionController.java`

```java
package com.garage.execution.controller;

import com.garage.execution.domain.ExecutionRequest;
import com.garage.execution.domain.ExecutionResult;
import com.garage.execution.service.ExecutionService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/execute")
public class ExecutionController {

    private final ExecutionService executionService;

    public ExecutionController(ExecutionService executionService) {
        this.executionService = executionService;
    }

    /**
     * Recebe código Java do jogador, compila, executa testes JUnit e retorna resultado.
     * Chamado internamente pelo FastAPI — não exposto diretamente ao browser.
     */
    @PostMapping
    public ResponseEntity<ExecutionResult> execute(@Valid @RequestBody ExecutionRequest request) {
        ExecutionResult result = executionService.execute(request);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}
```

---

### 5.10 `config/SandboxConfig.java`

```java
package com.garage.execution.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import java.util.List;

@Component
@ConfigurationProperties(prefix = "garage.sandbox")
public class SandboxConfig {
    private long timeoutMs = 5000;
    private long maxOutputBytes = 10240;
    private List<String> allowedPackages;
    private List<String> forbiddenPackages;

    // getters e setters omitidos por brevidade — usar Lombok @Data se preferir
    public long getTimeoutMs() { return timeoutMs; }
    public void setTimeoutMs(long t) { this.timeoutMs = t; }
    public long getMaxOutputBytes() { return maxOutputBytes; }
    public void setMaxOutputBytes(long m) { this.maxOutputBytes = m; }
    public List<String> getAllowedPackages() { return allowedPackages; }
    public void setAllowedPackages(List<String> a) { this.allowedPackages = a; }
    public List<String> getForbiddenPackages() { return forbiddenPackages; }
    public void setForbiddenPackages(List<String> f) { this.forbiddenPackages = f; }
}
```

---

### 5.11 `config/WebConfig.java`

```java
package com.garage.execution.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Só aceita chamadas do FastAPI (localhost) — jamais do browser diretamente.
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
            .allowedOrigins(
                "http://localhost:8000",   // FastAPI dev
                "https://garage-api.onrender.com"  // FastAPI prod
            )
            .allowedMethods("POST", "GET")
            .allowedHeaders("Content-Type", "X-Internal-Token");
    }
}
```

---

## 6. Exemplo de Test Suite — `intern_01_xerox_object_creation`

Arquivo: `src/main/java/com/garage/execution/suites/Intern01XeroxObjectCreationTest.java`

```java
package com.garage.execution.suites;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.lang.reflect.*;
import java.math.BigDecimal;

/**
 * Test suite para o desafio intern_01_xerox_object_creation.
 * Verifica que Account nasce válido e rejeita estado inválido.
 */
class Intern01XeroxObjectCreationTest {

    private Object createAccount(String id, BigDecimal balance) throws Exception {
        Class<?> clazz = Class.forName("Account");
        Constructor<?> ctor = clazz.getConstructor(String.class, BigDecimal.class);
        return ctor.newInstance(id, balance);
    }

    @Test
    @DisplayName("Account válida deve ser criada com sucesso")
    void test_valid_account_creation() throws Exception {
        Object account = createAccount("acc-1", new BigDecimal("100.00"));
        assertNotNull(account);
    }

    @Test
    @DisplayName("Id nulo deve lançar exceção")
    void test_null_id_throws() {
        assertThrows(Exception.class, () -> createAccount(null, new BigDecimal("100.00")));
    }

    @Test
    @DisplayName("Id vazio deve lançar exceção")
    void test_blank_id_throws() {
        assertThrows(Exception.class, () -> createAccount("  ", new BigDecimal("100.00")));
    }

    @Test
    @DisplayName("Balance negativo deve lançar exceção")
    void test_negative_balance_throws() {
        assertThrows(Exception.class, () -> createAccount("acc-1", new BigDecimal("-1.00")));
    }

    @Test
    @DisplayName("getId() retorna o id fornecido na construção")
    void test_getId_returns_correct_value() throws Exception {
        Object account = createAccount("acc-42", BigDecimal.TEN);
        Method getId = account.getClass().getMethod("getId");
        assertEquals("acc-42", getId.invoke(account));
    }

    @Test
    @DisplayName("getBalance() retorna o balance fornecido na construção")
    void test_getBalance_returns_correct_value() throws Exception {
        Object account = createAccount("acc-1", new BigDecimal("250.00"));
        Method getBal = account.getClass().getMethod("getBalance");
        assertEquals(new BigDecimal("250.00"), getBal.invoke(account));
    }
}
```

---

## 7. Integração no FastAPI (Python)

### 7.1 Novo caso de uso: `application/execute_code.py`

```python
"""Use case: proxy code execution to the Java Execution Service."""
import httpx
from typing import TypedDict


EXECUTION_SERVICE_URL = "http://localhost:8080"  # ou env var


class ExecuteCodeResult(TypedDict):
    compiled: bool
    tests_passed: int
    tests_total: int
    score_percent: int
    failures: list[str]
    feedback: str
    execution_time_ms: int


async def execute_code(challenge_id: str, player_code: str) -> ExecuteCodeResult:
    """Send player code to the Java Execution Service and return the result."""
    payload = {
        "challengeId": challenge_id,
        "playerCode": player_code,
        "language": "java17",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{EXECUTION_SERVICE_URL}/execute", json=payload)
        resp.raise_for_status()
        return resp.json()
```

### 7.2 Nova rota: `api/routes/game_routes.py` — endpoint `/api/execute-code`

```python
class ExecuteCodeRequest(BaseModel):
    session_id: str
    challenge_id: str
    player_code: str = Field(..., max_length=8000)


@router.post("/execute-code")
async def execute_code_endpoint(
    req: ExecuteCodeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Execute player Java code and return test results."""
    from app.application.execute_code import execute_code

    # Verificar que o desafio pertence à sessão atual
    player = _player_repo.find_by_session(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await execute_code(req.challenge_id, req.player_code)

    # Se 100% dos testes passaram, acionar o fluxo normal de submit_answer
    if result["score_percent"] == 100:
        _events.log("code_challenge_passed", {
            "user_id": current_user["sub"],
            "challenge_id": req.challenge_id,
        })

    return result
```

### 7.3 Atualizar `challenges.json` — novo tipo `"coding"`

```json
{
  "id": "intern_01_xerox_object_creation",
  "title": "Nascimento do Objeto",
  "type": "coding",
  "description": "Implemente a classe Account para que ela nasça sempre em estado válido.",
  "starter_code": "public class Account {\n    // implemente aqui\n}",
  "category": "domain_modeling",
  "required_stage": "Intern",
  "region": "Xerox PARC",
  "mentor": "The Craftsman",
  "points_on_correct": 200
}
```

---

## 8. Frontend — Monaco Editor

### 8.1 Adicionar Monaco ao HTML

```html
<!-- No <head> do index.html -->
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/monaco-editor@0.47.0/min/vs/editor/editor.main.css" />

<!-- No <body> -->
<div id="code-editor-container" style="display:none; width:100%; height:400px; border:1px solid #333;">
  <div id="monaco-editor" style="width:100%;height:100%;"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.47.0/min/vs/loader.js"></script>
<script>
require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.47.0/min/vs' }});
require(['vs/editor/editor.main'], function() {
    window.monacoEditor = monaco.editor.create(document.getElementById('monaco-editor'), {
        value: '',
        language: 'java',
        theme: 'vs-dark',
        fontSize: 14,
        minimap: { enabled: false },
        automaticLayout: true,
    });
});
</script>
```

### 8.2 Função de submissão no `game.js`

```javascript
async function submitCode(challengeId) {
    const code = window.monacoEditor.getValue();
    const sessionId = currentSession.id;

    const resp = await fetch('/api/execute-code', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify({
            session_id: sessionId,
            challenge_id: challengeId,
            player_code: code
        })
    });

    const result = await resp.json();
    displayCodeResult(result);

    if (result.score_percent === 100) {
        triggerChallengeComplete(challengeId);
    }
}

function displayCodeResult(result) {
    const panel = document.getElementById('result-panel');
    panel.innerHTML = `
        <h3>${result.score_percent === 100 ? '✅ PASSOU' : '❌ FALHOU'}</h3>
        <p>${result.feedback}</p>
        <p>Testes: ${result.tests_passed}/${result.tests_total}</p>
        ${result.failures.map(f => `<pre class="error">${f}</pre>`).join('')}
    `;
}
```

---

## 9. Dockerfile

```dockerfile
FROM eclipse-temurin:17-jdk-alpine AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN ./mvnw -q package -DskipTests

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /app/target/execution-service-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 10. Deploy (Render.com)

Adicionar ao `render.yaml` existente:

```yaml
- type: web
  name: garage-execution-service
  runtime: docker
  dockerfilePath: ./execution-service/Dockerfile
  dockerContext: ./execution-service
  envVars:
    - key: GARAGE_SANDBOX_TIMEOUT_MS
      value: 5000
    - key: INTERNAL_TOKEN
      generateValue: true
  plan: free
```

---

## 11. Mapa Completo de Desafios `coding` — 100% do Jogo (72 desafios)

> **Todos os 72 desafios do jogo ganham versão coding.**
> Cada linha mapeia: challenge_id existente → conceito Java 17 que o jogador implementa → o que o JUnit verifica.

---

### STAGE: Intern · Locação: Xerox PARC (1973)
*NPC: Alan Kay · Tema: "Tudo é um Objeto"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 1 | `intern_01_xerox_object_creation` | Classe `Account(String id, BigDecimal balance)` com validação no construtor | id nulo lança exceção; balance negativo lança exceção; objeto válido criado com sucesso |
| 2 | `intern_02_xerox_naming` | Método `int calculateElapsedDays(LocalDate start, LocalDate end)` com nomes revelando intenção | retorna dias corretos; `start == end` → 0; `end` antes de `start` → valor negativo |
| 3 | `intern_03_xerox_functions` | Extrair `validateInput()`, `calculatePrice()`, `applyDiscount()`, `saveOrder()`, `sendConfirmation()` de `processOrder()` | cada método existe e é chamado; nenhum método tem mais de 20 linhas; `processOrder()` apenas delega |

---

### STAGE: Intern · Locação: Apple Garage (1976)
*NPC: Steve Jobs & Wozniak · Tema: "Eficiência de Recursos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 4 | `intern_04_apple_hello_world` | Classe `HelloWorld` com `main(String[] args)` e `greet(String name): String` | `greet("Steve")` retorna `"Hello, Steve!"`; `greet(null)` lança `IllegalArgumentException` |
| 5 | `intern_05_apple_data_structures` | Classe `Stack<T>` com `push`, `pop`, `peek`, `isEmpty` usando array interno | push/pop LIFO correto; `pop()` em stack vazia lança `EmptyStackException`; `isEmpty()` retorna true/false corretos |
| 6 | `intern_06_apple_types` | Método `convertTemperature(double celsius): double` e `int toBits(byte b): int` | conversão Celsius→Fahrenheit correta; bit representation de byte correto; tipos primitivos usados adequadamente |

---

### STAGE: Junior · Locação: Microsoft (1975)
*NPC: Bill Gates · Tema: "Lógica de Negócios"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 7 | `junior_01_microsoft_domain` | Entidade `Product(String id, String name, BigDecimal price)` com encapsulamento (campos `private final`) | campos não acessíveis diretamente; getters retornam valores corretos; construtor rejeita preço negativo |
| 8 | `junior_02_microsoft_immutability` | Record Java 17: `record Money(BigDecimal amount, String currency)` com método `add(Money other): Money` | `add()` retorna novo objeto (não modifica o original); `amount` nulo lança exceção; moedas diferentes lançam exceção |
| 9 | `junior_03_microsoft_layers` | Interface `ProductRepository` com `save(Product p)`, `findById(String id): Optional<Product>`, `findAll(): List<Product>` + implementação `InMemoryProductRepository` | `save` + `findById` round-trip; `findById` de id inexistente retorna `Optional.empty()`; `findAll` retorna lista imutável |

---

### STAGE: Junior · Locação: Nubank (atual)
*NPC: David Vélez · Tema: "Fintech e Validação"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 10 | `junior_04_nubank_validation` | Classe `CreditCard` com validação de número Luhn, `expiryDate` futuro e `cvv` de 3 dígitos | número Luhn inválido lança exceção; `cvv` com 4 dígitos lança exceção; cartão vencido lança exceção; cartão válido criado |
| 11 | `junior_05_nubank_exceptions` | Hierarquia de exceções: `PaymentException` → `InsufficientFundsException` e `CardExpiredException`; método `processPayment(double amount)` que lança a correta | `InsufficientFundsException extends PaymentException` verificado via reflection; `processPayment(-1)` lança `IllegalArgumentException`; saldo insuficiente lança `InsufficientFundsException` |
| 12 | `junior_06_nubank_testing` | Escrever 4 testes JUnit 5 para a classe `TransferService` fornecida (código dado, testes faltando) | todos os 4 testes existem; cobrem caminho feliz, saldo insuficiente, conta inexistente e valor zero |

---

### STAGE: Junior · Locação: Disney (entretenimento)
*NPC: Walt Disney digital · Tema: "OOP — The Magical Kingdom"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 13 | `junior_07_disney_oop_encapsulation` | Classe `DisneyCharacter` com campos `private`, getters/setters com validação; `name` imutável após construção | setter de `name` inexiste (ou privado); getter retorna valor; campo direto inacessível via reflection com `setAccessible(false)` |
| 14 | `junior_08_disney_oop_interface` | Interface `Animatable` com `animate(): String` e `reset(): void`; classes `Princess` e `Villain` implementando | ambas implementam `Animatable`; `instanceof Animatable` true; `animate()` retorna string não vazia diferente entre classes |
| 15 | `junior_09_disney_oop_polymorphism` | Array `Animatable[]` com instâncias mistas; método `runShow(Animatable[] cast): List<String>` que chama `animate()` polimorfico | lista retorna um resultado por personagem; upcasting correto; nenhum cast explícito para subclasse dentro de `runShow` |

---

### STAGE: Mid · Locação: Google (1998)
*NPC: Larry Page & Sergey Brin · Tema: "Organizando a Informação Mundial"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 16 | `mid_01_google_hashmap` | Método `twoSum(int[] nums, int target): int[]` com `HashMap` (O(n)) | retorna índices corretos; funciona com negativos; nenhuma solução retorna array vazio; complexidade O(n) inferida (sem loop aninhado) |
| 17 | `mid_02_google_framework` | Anotação `@Component` simples + classe `SimpleContainer` com `register(Class<?> c)` e `get(Class<?> c): Object` | `get` retorna instância do tipo correto; segundo `get` retorna mesma instância (singleton); classe não anotada lança `IllegalArgumentException` |
| 18 | `mid_03_google_complexity` | Método `findDuplicates(int[] arr): List<Integer>` — proibido usar O(n²); deve usar `HashSet` | duplicatas corretas retornadas; array sem duplicatas retorna lista vazia; sem loop aninhado no bytecode (verificado via AST) |

---

### STAGE: Mid · Locação: Facebook (2004)
*NPC: Mark Zuckerberg · Tema: "Conexões e Escala Social"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 19 | `mid_04_facebook_tdd` | Escrever testes JUnit 5 **primeiro** para `UserService.register(String email, String password)` antes da implementação ser revelada | testa email inválido; testa senha fraca < 8 chars; testa email duplicado; testa cadastro bem-sucedido; 4 testes mínimos obrigatórios |
| 20 | `mid_05_facebook_graphs` | Classe `SocialGraph` com `addUser(int id)`, `addFriendship(int a, int b)`, `bfs(int start): List<Integer>` | BFS retorna nós em ordem de nível; grafo desconexo retorna apenas componente do `start`; `bfs` de nó inexistente lança exceção |
| 21 | `mid_06_facebook_concurrency` | Classe `ViewCounter` thread-safe com `increment()` e `getCount(): long` usando `AtomicLong`; teste com 100 threads fazendo 1000 incrementos cada | após execução concorrente `getCount() == 100_000`; sem `synchronized` keyword (deve usar atomic); sem race condition detectada |

---

### STAGE: Mid · Locação: IBM
*Tema: "Algoritmos Clássicos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 22 | `mid_07_ibm_stack_applications` | Método `isBalanced(String expr): boolean` usando `Deque<Character>` para verificar `()[]{}` | `"([])"` → true; `"([)]"` → false; string vazia → true; abertura sem fechamento → false |
| 23 | `mid_08_ibm_expression_parsing` | Método `evaluate(String expression): int` para expressões infix simples (`"3 + 5 * 2"`) respeitando precedência | `"3 + 5"` → 8; `"10 - 3 * 2"` → 4; `"2 * 3 + 4 / 2"` → 8; divisão inteira correta |
| 24 | `mid_09_ibm_time_complexity` | Método `binarySearch(int[] sortedArr, int target): int` iterativo (não recursivo) | elemento presente retorna índice correto; elemento ausente retorna -1; array de 1 elemento funciona; array vazio retorna -1 |

---

### STAGE: Senior · Locação: Amazon (1994)
*NPC: Jeff Bezos · Tema: "Escala Logística"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 25 | `senior_01_amazon_performance` | Classe `LRUCache(int capacity)` com `get(int key): int` e `put(int key, int value)` usando `LinkedHashMap` | capacity respeitada (elemento mais antigo evicted); `get` de chave inexistente retorna -1; `put` de chave existente atualiza e torna mais recente |
| 26 | `senior_02_amazon_twosum` | Método `productExceptSelf(int[] nums): int[]` sem divisão, O(n) | `[1,2,3,4]` → `[24,12,8,6]`; array com zero funciona; prefixo e sufixo calculados corretamente |
| 27 | `senior_03_amazon_resilience` | Classe `CircuitBreaker` com estados `CLOSED/OPEN/HALF_OPEN`; `call(Callable<T> action): T` com threshold de 3 falhas | 3 falhas consecutivas → `OPEN`; em `OPEN` lança `CircuitOpenException` sem executar action; após timeout → `HALF_OPEN` → sucesso fecha |

---

### STAGE: Senior · Locação: Mercado Livre
*NPC: Marcos Galperin · Tema: "E-commerce em Escala"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 28 | `senior_04_meli_idempotency` | Classe `IdempotentPaymentProcessor` com `process(String idempotencyKey, double amount): PaymentResult`; segunda chamada com mesmo key retorna resultado cacheado | segunda chamada NÃO executa lógica de pagamento (verificado com contador); mesmo resultado retornado; chave diferente processa normalmente |
| 29 | `senior_05_meli_cache` | Classe `TTLCache<K,V>(long ttlMs)` com `put(K,V)`, `get(K): Optional<V>`; entradas expiram após ttl | `get` após ttl retorna `Optional.empty()`; `get` dentro do ttl retorna valor; `put` renovado reinicia ttl |
| 30 | `senior_06_meli_sharding` | Classe `ConsistentHashRing` com `addNode(String node)`, `removeNode(String node)`, `getNode(String key): String` | mesma chave → mesmo nó (determinístico); remover nó redistribui apenas chaves daquele nó; adicionar nó não muda mapeamento da maioria |

---

### STAGE: Senior · Locação: JP Morgan
*NPC: Jamie Dimon · Tema: "Sistemas Financeiros Críticos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 31 | `senior_07_jpmorgan_consistency` | Classe `TwoPhaseCommit` com `prepare(): boolean`, `commit()`, `rollback()`; coordena 2 participantes | se `prepare()` de qualquer participante falha → `rollback()` chamado; se ambos preparam → `commit()` chamado; estado final consistente |
| 32 | `senior_08_jpmorgan_encryption` | Classe `AESCipher` com `encrypt(String plaintext, String key): String` e `decrypt(String ciphertext, String key): String` usando `javax.crypto` | `decrypt(encrypt(text, k), k)` == text; chave errada lança exceção; texto vazio encripta e decripta corretamente |
| 33 | `senior_09_jpmorgan_audit` | Classe `AuditLog` thread-safe com `record(String action, String userId)` e `getHistory(String userId): List<String>` | múltiplas threads gravando; histórico de usuário retorna apenas suas ações; log append-only (sem delete); ordem cronológica preservada |

---

### STAGE: Senior · Locação: PayPal (2000)
*NPC: Elon Musk jovem · Tema: "Missão Crítica e Segurança"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 34 | `senior_10_paypal_string_hashing` | Método `hash(String input): int` implementando djb2 manualmente (sem `String.hashCode()`) | mesma string → mesmo hash; strings diferentes → hashes diferentes (colisão mínima); `null` lança `NullPointerException` |
| 35 | `senior_11_paypal_anagram_fraud` | Método `detectAnagramPairs(List<String> transactions): List<String[]>` — retorna pares que são anagramas | `["listen","silent","hello"]` → 1 par; lista sem anagramas → lista vazia; case-insensitive |
| 36 | `senior_12_paypal_idempotency` | Classe `PaymentGateway` com `charge(String txId, double amount): Receipt`; replay do mesmo `txId` retorna mesmo `Receipt` sem reprocessar | `charge` duas vezes com mesmo txId → mesmo objeto; `chargeCount` interno não incrementa na segunda chamada; txId diferente → novo `Receipt` |

---

### STAGE: Senior · Locação: Netflix
*NPC: Reed Hastings · Tema: "Streaming em Escala"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 37 | `senior_13_netflix_sliding_window` | Método `maxSumSubarray(int[] nums, int k): int` usando sliding window O(n) | `[2,1,5,1,3,2]` k=3 → 9; janela maior que array lança exceção; array de zeros → 0 |
| 38 | `senior_14_netflix_recommendation` | Classe `RecommendationEngine` com `addView(String userId, String content, int rating)` e `recommend(String userId): List<String>` usando `PriorityQueue` | recomenda conteúdo com maior rating; não recomenda conteúdo já visto; lista vazia para usuário sem histórico |
| 39 | `senior_15_netflix_time_series` | Classe `MovingAverage(int windowSize)` com `next(double value): double` usando `ArrayDeque` | média correta após janela cheia; janela parcial usa apenas valores disponíveis; tamanho 1 → retorna o próprio valor |

---

### STAGE: Staff · Locação: Tesla
*NPC: Elon Musk · Tema: "CAP Theorem e Sistemas Distribuídos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 40 | `staff_01_tesla_cap` | Enum `Consistency` com `STRONG/EVENTUAL`; classe `DistributedStore` com `setConsistencyModel(Consistency c)`, `write(String k, String v)`, `read(String k): String` — CP retorna só após "quorum" | CP: `read` após `write` sempre retorna valor atual; AP: `read` pode retornar valor desatualizado (simulado); modelos não intercambiáveis após dados escritos |
| 41 | `staff_02_tesla_event_sourcing` | Classe `BankAccount` com `List<Event> events`; métodos `deposit(double)`, `withdraw(double)`, reconstituível via `replay(List<Event>)` | `replay` reconstrói saldo idêntico; eventos imutáveis (Record); ordem dos eventos importa (testar inversão) |
| 42 | `staff_03_tesla_redundancy` | Classe `LeaderElection` com `register(String nodeId)`, `elect(): String`, `heartbeat(String nodeId)`, `checkHealth(): String` | sem heartbeat após timeout → novo líder eleito; nó com heartbeat recente permanece líder; sem nós registrados lança exceção |

---

### STAGE: Staff · Locação: Itaú
*NPC: Roberto Setubal · Tema: "Sistemas Legados e Observabilidade"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 43 | `staff_04_itau_legacy` | Padrão Strangler Fig: interface `LegacyPaymentPort`, classe `LegacyPaymentAdapter(OldSystem old)` que adapta a nova interface | adapter delega para `OldSystem`; nova interface não depende de `OldSystem`; `OldSystem` mockável via adapter |
| 44 | `staff_05_itau_observability` | Classe `MetricsCollector` com `record(String metric, double value)`, `average(String metric): double`, `percentile(String metric, int p): double` | média correta; p95 correto com 100 amostras; `average` de métrica inexistente retorna 0.0 |
| 45 | `staff_06_itau_security` | Classe `JwtValidator` com `validate(String token, String secret): Claims`; verifica assinatura, expiração e estrutura | token válido retorna claims; token expirado lança `TokenExpiredException`; assinatura inválida lança `InvalidSignatureException` |

---

### STAGE: Staff · Locação: Uber
*NPC: Travis Kalanick · Tema: "Real-time e Geoespacial"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 46 | `staff_07_uber_realtime` | Classe `EventBus` com `subscribe(String topic, Consumer<String> handler)`, `publish(String topic, String event)` usando `ConcurrentHashMap<String, List<Consumer>>` | subscriber recebe evento após `publish`; múltiplos subscribers no mesmo tópico todos recebem; tópico sem subscriber não lança exceção |
| 47 | `staff_08_uber_geospatial` | Método `haversineDistance(double lat1, double lon1, double lat2, double lon2): double` retorna distância em km | SP→RJ ≈ 357 km (±5%); mesmo ponto → 0.0; pontos antipodais ≈ 20004 km |
| 48 | `staff_09_uber_consistency` | Padrão Saga: classe `RideBookingSaga` com `bookDriver()`, `chargeCreditCard()`, `assignRide()` e compensações correspondentes `releaseDriver()`, `refundCard()`, `cancelRide()`; se `chargeCreditCard()` falha, `releaseDriver()` é chamado | compensação correta acionada em cada falha; ordem exata de compensação verificada; sucesso completo não chama compensações |

---

### STAGE: Staff · Locação: SpaceX
*NPC: Elon Musk · Tema: "Missão Crítica — Zero Defeitos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 49 | `staff_10_spacex_deduplication` | Classe `BloomFilter(int size, int hashFunctions)` com `add(String item)`, `mightContain(String item): boolean` | item adicionado → `mightContain` true; item nunca adicionado → `mightContain` geralmente false (falso positivo aceitável); estrutura não armazena item real |
| 50 | `staff_11_spacex_set_operations` | Classe `SetOps<T>` com `union(Set<T> a, Set<T> b)`, `intersection(Set<T> a, Set<T> b)`, `difference(Set<T> a, Set<T> b)` todos retornando novo `Set<T>` imutável | union correto; intersection somente elementos em ambos; difference elementos só em A; conjuntos originais não modificados |
| 51 | `staff_12_spacex_realtime_constraints` | Classe `TokenBucketRateLimiter(int capacity, int refillPerSecond)` com `tryAcquire(): boolean` | burst até capacity permitido; após capacity → false; refill ocorre após 1s (simulado); thread-safe |

---

### STAGE: Staff · Locação: Nvidia
*Tema: "Algoritmos de Ordenação — GPU Mindset"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 52 | `staff_13_nvidia_merge_vs_quick` | `mergeSort(int[] arr): int[]` retornando novo array ordenado (não in-place) | array ordenado corretamente; array original não modificado; array vazio retorna vazio; array de 1 elemento retorna mesmo array |
| 53 | `staff_14_nvidia_divide_conquer` | `quickSort(int[] arr, int low, int high)` in-place com pivot como elemento do meio | array ordenado após chamada; funciona com duplicatas; array de 1 elemento inalterado; partição em torno do pivot verificada |
| 54 | `staff_15_nvidia_sorting_stability` | `stableSort(Person[] people)` por `age` preservando ordem relativa de pessoas com mesma idade usando merge sort | pessoas com mesma idade mantêm ordem original; ordenação por age correta; método deve ser merge sort (verificado que não usa `Arrays.sort`) |

---

### STAGE: Staff · Locação: Aurora Labs (avançado)
*Tema: "Teoria dos Grafos"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 55 | `staff_16_aurora_labs_graph_representation` | Classe `Graph` com representação por lista de adjacência; `addEdge(int u, int v)`, `getNeighbors(int v): List<Integer>`, `hasEdge(int u, int v): boolean` | `hasEdge` correto; grafo não-direcionado: `addEdge(1,2)` → `hasEdge(2,1)` true; `getNeighbors` retorna cópia (não referência interna) |
| 56 | `staff_17_aurora_labs_bfs_vs_dfs` | Métodos `bfs(int start): List<Integer>` e `dfs(int start): List<Integer>` na mesma classe `Graph` | BFS retorna nós em ordem de nível; DFS retorna em ordem de profundidade; nó já visitado não duplicado; grafo com ciclo não entra em loop infinito |
| 57 | `staff_18_aurora_labs_connection_graphs` | Algoritmo de Kruskal: `minimumSpanningTree(int[][] edges, int nodes): List<int[]>` onde edges são `[u, v, weight]` | MST tem `nodes-1` arestas; soma dos pesos é o mínimo possível; grafo desconexo retorna floresta; sem arestas duplicadas |

---

### STAGE: Principal · Locação: Santander
*NPC: Ana Botín · Tema: "Compliance, Privacidade e Regulação"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 58 | `principal_01_santander_compliance` | Classe `DataMasker` com `maskCPF(String cpf): String` → `"***.***.***-XX"`, `maskEmail(String email): String`, `maskCard(String card): String` | CPF mascarado corretamente; email apenas domínio visível; card: apenas 4 últimos dígitos; `null` input lança exceção |
| 59 | `principal_02_santander_privacy` | Anotação `@Sensitive` + processador que usa reflection para mascarar campos anotados ao serializar objeto para `Map<String,Object>` | campos anotados mascarados; campos não anotados passam inalterados; funciona em subclasses |
| 60 | `principal_03_santander_resilience` | Padrão Bulkhead: `BulkheadExecutor(int maxConcurrent)` com `submit(Callable<T>): Future<T>`; lança `BulkheadFullException` quando `maxConcurrent` excedido | `maxConcurrent` threads simultâneas aceitas; (maxConcurrent + 1) → exceção; após thread terminar → nova thread aceita; thread-safe |

---

### STAGE: Principal · Locação: Bradesco
*NPC: Octavio de Lazari · Tema: "Open Banking e IA"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 61 | `principal_04_bradesco_scaling` | Classe `LoadBalancer` com `addServer(String server)`, `removeServer(String server)`, `nextServer(): String` usando Round-Robin thread-safe | distribuição uniforme com 3 servidores em 300 chamadas; `removeServer` em uso → redistribui; `nextServer` com 0 servidores lança exceção |
| 62 | `principal_05_bradesco_openbanking` | Interface `OpenBankingAdapter` com `getBalance(String accountId): Money`, `transfer(String from, String to, Money amount): TransferResult`; implementação `BradescoOpenBankingAdapter` | implementa interface; `transfer` com saldo insuficiente retorna `TransferResult.FAILED`; `accountId` inválido lança `AccountNotFoundException` |
| 63 | `principal_06_bradesco_ai` | Padrão Strategy: interface `AIModelStrategy` com `predict(String input): String`; classes `OpenAIStrategy`, `AnthropicStrategy`, `FallbackStrategy`; classe `AIRouter` que tenta estratégias em ordem até sucesso | `AIRouter` tenta primeira estratégia; se lança exceção, tenta segunda; todas falhando → `FallbackStrategy` sempre retorna resposta |

---

### STAGE: Principal · Locação: Cloud Valley
*Tema: "Arquitetura de Nuvem e DDD Avançado"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 64 | `principal_07_cloud_retry` | Classe `RetryPolicy(int maxAttempts, long baseDelayMs, double multiplier)` com `execute(Callable<T>): T`; exponential backoff com jitter | 3 falhas → lança `MaxRetriesExceededException`; delay entre tentativas cresce exponencialmente; sucesso na 2ª tentativa → retorna valor sem lançar exceção |
| 65 | `principal_08_cloud_legacy` | Anti-Corruption Layer: interface `ModernPaymentPort`, classe `LegacySystemACL` que traduz objetos `LegacyPaymentDTO` → `ModernPaymentCommand` | tradução de campos correta; nenhum tipo do sistema legado vaza além do ACL; `null` em campo legacy resulta em default seguro no moderno |
| 66 | `principal_09_cloud_oath` | Aggregate Root completo `CustomerAccount` com: `List<DomainEvent> uncommittedEvents`, `debit(Money)`, `credit(Money)`, `close()`, invariante de saldo positivo e estado de conta aberta | debitar conta fechada lança `AccountClosedException`; saldo negativo lança `InsufficientFundsException`; cada operação emite `DomainEvent` correto; `uncommittedEvents` acumula e pode ser limpo |

---

### STAGE: Principal · Locação: Gemini (avançado)
*Tema: "Estruturas de Dados Avançadas"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 67 | `principal_10_gemini_heap_property` | Classe `MinHeap` com `insert(int val)`, `extractMin(): int`, `peek(): int` usando array interno | `extractMin` sempre retorna o mínimo; após N inserts + N extractions → array está ordenado; `extractMin` em heap vazio lança `EmptyHeapException` |
| 68 | `principal_11_gemini_dijkstra` | Método `dijkstra(int[][] graph, int src): int[]` retornando array de distâncias mínimas de `src` a todos os nós | distâncias corretas em grafo de 5 nós; nó inacessível retorna `Integer.MAX_VALUE`; nó origem tem distância 0; sem arestas negativas (verificado) |
| 69 | `principal_12_gemini_comparable` | Classe `VersionNumber(String version)` implementando `Comparable<VersionNumber>` para comparar versões semver `"1.2.3"` | `"1.2.3" < "1.2.4"` → `compareTo` < 0; `"2.0.0" > "1.99.99"` → `compareTo` > 0; versões iguais → 0; `Collections.sort` ordena lista corretamente |

---

### STAGE: Principal · Locação: Aurora Labs (boss final)
*NPC: O Mentor · Tema: "Dynamic Programming — A Prova Final"*

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 70 | `principal_13_nexus_labs_dp_concept` | Método `fibonacci(int n): long` com memoization usando `Map<Integer,Long>` (não recursão pura) | `fibonacci(10)` == 55; `fibonacci(50)` < 100ms (sem memoization seria impossível); `fibonacci(0)` == 0; `fibonacci(1)` == 1 |
| 71 | `principal_14_nexus_labs_dp_vs_greedy` | Método `knapsack(int[] weights, int[] values, int capacity): int` DP 0/1 (não greedy) | resposta ótima para caso clássico `[2,3,4,5]` `[3,4,5,6]` capacity 8 → 10; capacidade 0 → 0; itens maiores que capacidade ignorados |
| 72 | `principal_15_nexus_labs_memoization` | Método `coinChange(int[] coins, int amount): int` — número mínimo de moedas; DP bottom-up | `coins=[1,5,11]` amount=15 → 3; impossível → -1; amount=0 → 0; solução deve ser bottom-up (sem stack overflow em amount grande) |

---

### STAGE: Principal · Locação: ∞ Bio Code Technology (2026) — BOSS FINAL
*CEO & Mentor: Cezi Cola · Senior Software Engineer · Símbolo: ∞*
*Tema: "O Círculo Se Fecha — Você É o Sistema Agora"*

> O jogador percorreu 53 anos de história da computação (Xerox PARC 1973 → Bio Code Technology 2026).
> Esta é a locação final. Não há próxima empresa. Há apenas a missão.

| # | challenge_id | O que o jogador implementa | O que o JUnit verifica |
|---|-------------|---------------------------|------------------------|
| 73 | `principal_16_biocode_platform_architecture` | Classe `PluginRegistry` com `register(String name, Class<?> pluginClass)` e `execute(String name, Object context): Object`; núcleo imutável, plugins extensíveis | novo plugin registrado é executado corretamente; registrar dois plugins com mesmo nome lança `DuplicatePluginException`; remover plugin e re-registrar funciona; core não depende de nenhuma classe concreta de plugin |
| 74 | `principal_17_biocode_infinite_systems` | Classe `SelfHealingExecutor` combinando `CircuitBreaker` + `RetryPolicy` + `Bulkhead` + `Fallback`; método `execute(Callable<T> action, Supplier<T> fallback): T` | 3 falhas → circuit abre → fallback é chamado; após timeout → half-open → sucesso fecha; bulkhead com capacity 2 rejeita terceira chamada concorrente; fallback NUNCA lança exceção |
| 75 | `principal_18_biocode_the_circle` | Aggregate Root `CareerJourney` com `List<CareerEvent> events`; métodos `promote(CareerStage to)`, `completeChallenge(String id)`, `replay(List<CareerEvent>): CareerJourney` que reconstrói estado do zero | `replay` produz mesmo estado que operações diretas; promover sem completar N desafios lança `PromotionNotEarnedException`; cada operação emite `CareerEvent` correto; `CareerJourney` nunca retrocede de stage |

---

**Total: 75 desafios · 6 stages · 24 regiões · 100% do jogo coberto**
**Pontuação máxima possível: Bio Code Technology = 1.300 pts (400 + 400 + 500)**

---

## 12. Checklist de Implementação (Ordem de Execução)

```
FASE 1 — Execution Service (Java) — base funcional
□ 1.  Criar diretório execution-service/
□ 2.  Criar pom.xml (seção 5.1)
□ 3.  Criar application.yml (seção 5.2)
□ 4.  Implementar ExecutionServiceApplication (5.3)
□ 5.  Implementar Records de domínio: ExecutionRequest, ExecutionResult (5.4, 5.5)
□ 6.  Implementar JavaCompilerService — compilação in-memory (5.6)
□ 7.  Implementar TestRunnerService — JUnit 5 launcher (5.7)
□ 8.  Implementar ExecutionService — orquestração + timeout (5.8)
□ 9.  Implementar ExecutionController — POST /execute (5.9)
□ 10. Implementar SandboxConfig + WebConfig (5.10, 5.11)
□ 11. Criar test suite de validação do próprio serviço
□ 12. mvn spring-boot:run — testar POST /execute manualmente com curl
□ 13. Confirmar health check: GET /execute/health → "OK"

FASE 2 — Test Suites (uma por desafio — 72 arquivos Java)
  Intern (6 suites):
□ 14. Intern01XeroxObjectCreationTest.java
□ 15. Intern02XeroxNamingTest.java
□ 16. Intern03XeroxFunctionsTest.java
□ 17. Intern04AppleHelloWorldTest.java
□ 18. Intern05AppleDataStructuresTest.java
□ 19. Intern06AppleTypesTest.java
  Junior (9 suites):
□ 20. Junior01MicrosoftDomainTest.java ... Junior09DisneyOopPolymorphismTest.java
  Mid (9 suites):
□ 21. Mid01GoogleHashmapTest.java ... Mid09IbmTimeComplexityTest.java
  Senior (15 suites):
□ 22. Senior01AmazonPerformanceTest.java ... Senior15NetflixTimeSeriesTest.java
  Staff (18 suites):
□ 23. Staff01TeslaCapTest.java ... Staff18AuroraLabsConnectionGraphsTest.java
  Principal (15 suites):
□ 24. Principal01SantanderComplianceTest.java ... Principal15NexusLabsMemoizationTest.java

FASE 3 — Integração FastAPI
□ 25. Criar application/execute_code.py — proxy para o Java service (seção 7.1)
□ 26. Adicionar POST /api/execute-code ao game_routes.py (seção 7.2)
□ 27. Adicionar campos "type", "starter_code" ao challenges.json (72 entradas)
□ 28. Atualizar domain/challenge.py — suportar type + starter_code
□ 29. Atualizar infrastructure/repositories/challenge_repository.py
□ 30. Escrever testes Python para execute_code use case (100% coverage)

FASE 4 — Frontend
□ 31. Adicionar Monaco Editor ao index.html (seção 8.1)
□ 32. Implementar submitCode() e displayCodeResult() em game.js (seção 8.2)
□ 33. Adaptar canvas game loop: quando type=="coding" → abre Monaco Editor
□ 34. Adicionar painel de resultado com feedback e erros JUnit
□ 35. Testar fluxo completo: browser → Monaco → FastAPI → Java → resultado visual

FASE 5 — Deploy e Validação
□ 36. Criar Dockerfile para execution-service (seção 9)
□ 37. Adicionar serviço ao render.yaml (seção 10)
□ 38. Configurar INTERNAL_TOKEN em ambos os serviços (.env)
□ 39. Deploy no Render.com
□ 40. Smoke test de todas as 6 stages (1 desafio por stage em produção)
□ 41. Validar timeout de 5s funcionando (submeter código com loop infinito)
□ 42. Validar sandboxing (submeter código com java.io.File — deve ser bloqueado)
```

---

## 13. Decisões de Arquitetura e Trade-offs

| Decisão | Alternativa Rejeitada | Motivo |
|---------|----------------------|--------|
| `javax.tools` em memória | Escrever .java em disco e executar `javac` | Sem I/O de disco, mais rápido, sem limpeza de temp files |
| Spring Boot 3.2 (Java 17) | Java 21 + Virtual Threads | Render free tier mais estável com 17; migrar para 21 quando estabilizar |
| FastAPI como proxy para Java | Expor Java direto ao browser | Java não conhece JWT; FastAPI valida auth antes de encaminhar |
| Timeout via `Future.get(timeout)` | `Thread.interrupt()` manual | `Future` é idiomático, testável, cancela a thread limpo |
| Test suites como classes Java compiladas | DSL de yaml/JSON para testes | Java é tipado — erros de test suite são capturados em compile-time |
| Monaco Editor via CDN | CodeMirror embutido | Monaco é o mesmo editor do VS Code — experiência familiar para devs |

---

*Documento gerado em 27/02/2026 · CeziCola · Bio Code Technology Ltda*
*Próxima ação: executar Checklist Fase 1, item 1 — `mkdir execution-service`*
