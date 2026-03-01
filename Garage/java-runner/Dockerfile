# ============================================================
# 404 Garage — Java Runner Service
# Multi-stage build: Maven build + slim JRE runtime
# ============================================================

# ── Stage 1: Build the Spring Boot fat-jar ─────────────────────────────────
FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /build
# Cache dependency layer separately from source
COPY pom.xml .
RUN mvn dependency:go-offline -q

COPY src ./src
RUN mvn package -DskipTests -q

# ── Stage 2: Minimal runtime with full JDK (javac required at runtime!) ─────
# We need JDK (not just JRE) because we call javac to compile player code.
FROM eclipse-temurin:17-jdk-jammy

WORKDIR /app
COPY --from=build /build/target/java-runner-1.0.0.jar app.jar

# Smoke-test: javac must be in PATH in this image
RUN javac -version

EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
