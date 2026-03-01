package com.garage.runner.controller;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import com.garage.runner.model.RunJavaRequest;
import com.garage.runner.model.RunJavaResponse;

/**
 * Core endpoint: POST /run-java
 *
 * Receives Java 17 source code, compiles it with the JDK's own javac
 * (always available since this service runs inside eclipse-temurin:17),
 * executes the .class file, and returns the real compiler/JVM output
 * so the 404 Garage IDE can display authentic diagnostics.
 *
 * Security model (process-level isolation):
 *  - Every request uses an isolated temp directory (deleted in finally block).
 *  - Compilation and execution have separate wall-clock timeouts.
 *  - JVM memory is capped: -Xmx128m heap, -Xss512k stack.
 *  - stdout + stderr are capped at MAX_OUTPUT_BYTES to prevent memory exhaustion.
 *  - Shared secret header (X-Runner-Secret) checked when RUNNER_SECRET is set.
 */
@RestController
@CrossOrigin(origins = "*")   // Python proxy calls this service
public class RunnerController {

    private static final Logger log = LoggerFactory.getLogger(RunnerController.class);

    // ── Configuration (overridable via env vars) ──────────────────────────

    @Value("${runner.compile-timeout-seconds:15}")
    private long compileTimeoutSeconds;

    @Value("${runner.run-timeout-seconds:10}")
    private long runTimeoutSeconds;

    @Value("${runner.max-output-bytes:102400}")   // 100 KB
    private int maxOutputBytes;

    @Value("${runner.secret:}")   // empty = no auth required
    private String runnerSecret;

    // ── Regex to extract public class name ───────────────────────────────

    private static final Pattern CLASS_NAME_RE =
        Pattern.compile("\\bpublic\\s+class\\s+(\\w+)");

    // ── Endpoints ─────────────────────────────────────────────────────────

    /**
     * Health check / smoke-test.
     * Returns javac version so the Python service can verify Java is reachable.
     */
    @GetMapping("/health")
    public ResponseEntity<Object> health() {
        String version = detectJavacVersion();
        return ResponseEntity.ok(java.util.Map.of(
            "status",        "ok",
            "javac_version", version,
            "java_home",     System.getProperty("java.home", "(not set)")
        ));
    }

    /**
     * Compile and execute Java 17 source code.
     * Body: { "code": "...", "stdinInput": "..." (optional) }
     */
    @PostMapping("/run-java")
    public ResponseEntity<RunJavaResponse> runJava(
            @RequestHeader(value = "X-Runner-Secret", required = false) String secret,
            @RequestBody RunJavaRequest req) {

        // ── Optional shared-secret guard ──────────────────────────────────
        if (runnerSecret != null && !runnerSecret.isBlank()) {
            if (!runnerSecret.equals(secret)) {
                return ResponseEntity.status(403)
                    .body(RunJavaResponse.error("Acesso negado ao serviço de compilação.", 0, ""));
            }
        }

        if (req.getCode() == null || req.getCode().isBlank()) {
            return ResponseEntity.badRequest()
                .body(RunJavaResponse.error("Código Java não fornecido.", 0, detectJavacVersion()));
        }

        long tStart = System.currentTimeMillis();
        Path tmpDir = null;

        try {
            tmpDir = Files.createTempDirectory("garage_java_");
            String code       = req.getCode();
            String className  = extractClassName(code);
            String fileName   = className + ".java";
            Path   javaFile   = tmpDir.resolve(fileName);
            String javacVer   = detectJavacVersion();

            // Write source file
            Files.writeString(javaFile, code, StandardCharsets.UTF_8);

            // ── Step 1: Compile ───────────────────────────────────────────
            Process compileProc = new ProcessBuilder(
                    "javac", "--release", "17", "-encoding", "UTF-8", fileName)
                .directory(tmpDir.toFile())
                .redirectErrorStream(false)
                .start();

            // Read streams in background threads BEFORE waitFor() to prevent
            // deadlock when output exceeds OS pipe buffer (~64 KB on Linux).
            StringBuilder compileOutBuf = new StringBuilder();
            StringBuilder compileErrBuf = new StringBuilder();
            Thread compileOutThr = streamReader(compileProc.getInputStream(), compileOutBuf);
            Thread compileErrThr = streamReader(compileProc.getErrorStream(), compileErrBuf);
            compileOutThr.start();
            compileErrThr.start();

            boolean compileFinished = compileProc.waitFor(compileTimeoutSeconds, TimeUnit.SECONDS);
            if (!compileFinished) {
                compileProc.destroyForcibly();
                long elapsed = System.currentTimeMillis() - tStart;
                // Return compile_ok=false with empty compile_error so the
                // frontend Turbo Engine fallback handles the UX gracefully.
                RunJavaResponse tr = new RunJavaResponse();
                tr.setOk(false);
                tr.setCompileOk(false);
                tr.setCompileError("");  // intentionally empty — frontend handles messaging
                tr.setStdout("");
                tr.setStderr("");
                tr.setExitCode(1);
                tr.setElapsedMs(elapsed);
                tr.setJavacVersion(javacVer);
                return ResponseEntity.ok(tr);
            }
            compileOutThr.join(2000L);
            compileErrThr.join(2000L);

            String rawCompileErrors = (compileOutBuf.toString() + compileErrBuf.toString()).trim();

            if (compileProc.exitValue() != 0) {
                // Strip absolute temp path from error messages
                String cleanErrors = rawCompileErrors
                    .replace(tmpDir.toString() + File.separator, "")
                    .replace(tmpDir.toString() + "/", "");
                cleanErrors = truncate(cleanErrors);
                long elapsed = System.currentTimeMillis() - tStart;

                RunJavaResponse resp = new RunJavaResponse();
                resp.setOk(false);
                resp.setCompileOk(false);
                resp.setCompileError(cleanErrors);
                resp.setExitCode(compileProc.exitValue());
                resp.setElapsedMs(elapsed);
                resp.setJavacVersion(javacVer);
                return ResponseEntity.ok(resp);
            }

            // ── Step 2: Run ───────────────────────────────────────────────
            ProcessBuilder runPb = new ProcessBuilder(
                    "java",
                    "-Xmx128m", "-Xss512k",
                    "-Dfile.encoding=UTF-8",
                    "-Djava.net.preferIPv4Stack=true",
                    "-cp", ".",
                    className)
                .directory(tmpDir.toFile())
                .redirectErrorStream(false);

            Process runProc = runPb.start();

            // Start stream readers BEFORE writing stdin and before waitFor()
            // to prevent pipe-buffer deadlock.
            StringBuilder runOutBuf = new StringBuilder();
            StringBuilder runErrBuf = new StringBuilder();
            Thread runOutThr = streamReader(runProc.getInputStream(), runOutBuf);
            Thread runErrThr = streamReader(runProc.getErrorStream(), runErrBuf);
            runOutThr.start();
            runErrThr.start();

            // Pipe optional stdin
            if (req.getStdinInput() != null && !req.getStdinInput().isBlank()) {
                try (OutputStream stdin = runProc.getOutputStream()) {
                    stdin.write(req.getStdinInput().getBytes(StandardCharsets.UTF_8));
                }
            } else {
                runProc.getOutputStream().close();
            }

            boolean runFinished = runProc.waitFor(runTimeoutSeconds, TimeUnit.SECONDS);
            if (!runFinished) {
                runProc.destroyForcibly();
                long elapsed = System.currentTimeMillis() - tStart;

                RunJavaResponse resp = new RunJavaResponse();
                resp.setOk(false);
                resp.setCompileOk(true);
                resp.setCompileError("");
                resp.setStdout("[Programa encerrado: tempo limite de execução excedido (" + runTimeoutSeconds + "s)]");
                resp.setExitCode(1);
                resp.setElapsedMs(elapsed);
                resp.setJavacVersion(javacVer);
                return ResponseEntity.ok(resp);
            }
            runOutThr.join(2000L);
            runErrThr.join(2000L);

            String stdout = truncate(runOutBuf.toString());
            String stderr = truncate(runErrBuf.toString());
            int    exitCode = runProc.exitValue();
            long   elapsed  = System.currentTimeMillis() - tStart;

            RunJavaResponse resp = new RunJavaResponse();
            resp.setOk(exitCode == 0);
            resp.setCompileOk(true);
            resp.setStdout(stdout);
            resp.setStderr(stderr);
            resp.setExitCode(exitCode);
            resp.setElapsedMs(elapsed);
            resp.setJavacVersion(javacVer);
            return ResponseEntity.ok(resp);

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            long elapsed = System.currentTimeMillis() - tStart;
            return ResponseEntity.ok(RunJavaResponse.error("Execução interrompida.", elapsed, ""));
        } catch (IOException e) {
            long elapsed = System.currentTimeMillis() - tStart;
            log.error("IO error in run-java", e);
            return ResponseEntity.ok(RunJavaResponse.error(
                "Erro interno do servidor de compilação: " + e.getMessage(), elapsed, ""));
        } finally {
            deleteTempDir(tmpDir);
        }
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    private String extractClassName(String code) {
        Matcher m = CLASS_NAME_RE.matcher(code);
        return m.find() ? m.group(1) : "Main";
    }

    private String readStream(InputStream is) throws IOException {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(is, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append("\n");
            }
            return sb.toString();
        }
    }

    /**
     * Returns a daemon thread that drains an InputStream into a StringBuilder.
     * Must be started before calling Process.waitFor() to prevent pipe-buffer deadlock.
     */
    private Thread streamReader(InputStream is, StringBuilder out) {
        Thread t = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    out.append(line).append("\n");
                }
            } catch (IOException ignored) {}
        });
        t.setDaemon(true);
        return t;
    }

    private String truncate(String text) {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= maxOutputBytes) return text;
        return new String(bytes, 0, maxOutputBytes, StandardCharsets.UTF_8)
            + "\n\n[... saída truncada: limite de saída atingido ...]";
    }

    private String detectJavacVersion() {
        try {
            Process p = new ProcessBuilder("javac", "-version")
                .redirectErrorStream(true)
                .start();
            p.waitFor(5, TimeUnit.SECONDS);
            return readStream(p.getInputStream()).trim();
        } catch (Exception e) {
            return "unavailable";
        }
    }

    private void deleteTempDir(Path dir) {
        if (dir == null) return;
        try {
            Files.walk(dir)
                .sorted(java.util.Comparator.reverseOrder())
                .map(Path::toFile)
                .forEach(File::delete);
        } catch (IOException e) {
            log.warn("Failed to clean temp dir: {}", dir, e);
        }
    }
}
