package com.garage.runner.model;

/**
 * Request payload sent by the Python backend (or directly by the frontend in dev mode).
 */
public class RunJavaRequest {

    private String code;
    private String stdinInput;  // optional stdin to pipe to the program

    public String getCode()            { return code; }
    public void   setCode(String code) { this.code = code; }

    public String getStdinInput()                  { return stdinInput; }
    public void   setStdinInput(String stdinInput) { this.stdinInput = stdinInput; }
}
