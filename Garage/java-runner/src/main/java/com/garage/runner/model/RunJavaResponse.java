package com.garage.runner.model;

/**
 * Response returned to the Python backend after compiling and running Java code.
 * Schema is intentionally identical to the Python RunJavaResponse so the Python
 * proxy can forward the JSON transparently without any transformation.
 */
public class RunJavaResponse {

    private boolean ok;
    private boolean compileOk;
    private String  stdout        = "";
    private String  stderr        = "";
    private String  compileError  = "";
    private int     exitCode      = 1;
    private long    elapsedMs     = 0;
    private String  javacVersion  = "";

    // ── Getters ────────────────────────────────────────────────────────────

    public boolean isOk()            { return ok; }
    public boolean isCompileOk()     { return compileOk; }
    public String  getStdout()       { return stdout; }
    public String  getStderr()       { return stderr; }
    public String  getCompileError() { return compileError; }
    public int     getExitCode()     { return exitCode; }
    public long    getElapsedMs()    { return elapsedMs; }
    public String  getJavacVersion() { return javacVersion; }

    // ── Setters ────────────────────────────────────────────────────────────

    public void setOk(boolean ok)                       { this.ok = ok; }
    public void setCompileOk(boolean compileOk)         { this.compileOk = compileOk; }
    public void setStdout(String stdout)                { this.stdout = stdout != null ? stdout : ""; }
    public void setStderr(String stderr)                { this.stderr = stderr != null ? stderr : ""; }
    public void setCompileError(String compileError)    { this.compileError = compileError != null ? compileError : ""; }
    public void setExitCode(int exitCode)               { this.exitCode = exitCode; }
    public void setElapsedMs(long elapsedMs)            { this.elapsedMs = elapsedMs; }
    public void setJavacVersion(String javacVersion)    { this.javacVersion = javacVersion != null ? javacVersion : ""; }

    // ── Builder-style factory ──────────────────────────────────────────────

    public static RunJavaResponse error(String compileError, long elapsedMs, String javacVersion) {
        RunJavaResponse r = new RunJavaResponse();
        r.ok            = false;
        r.compileOk     = false;
        r.compileError  = compileError;
        r.elapsedMs     = elapsedMs;
        r.javacVersion  = javacVersion != null ? javacVersion : "";
        return r;
    }
}
