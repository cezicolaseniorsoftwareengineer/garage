# ============================================================
# 404 Garage — Production Image
# Base: python:3.13-slim (Debian Bookworm)
# Java: OpenJDK 17 LTS installed via apt — guaranteed to work
#       on Render.com regardless of buildpack configuration.
# ============================================================

FROM python:3.13-slim

# ── System deps + Java 17 ──────────────────────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y -q --no-install-recommends \
        openjdk-17-jdk-headless \
        curl \
        && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Java environment ──────────────────────────────────────────────────────
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Smoke-test: fail the image build immediately if javac/java are missing
RUN javac -version && java -version

# ── Python dependencies ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ─────────────────────────────────────────────────────────────
COPY . .

# ── Runtime ───────────────────────────────────────────────────────────────
EXPOSE 10000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
