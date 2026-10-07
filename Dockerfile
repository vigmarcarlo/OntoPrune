# Generated for Glama & Containerized MCP environments
FROM python:3.12-slim

ENV PATH="/usr/local/bin:$PATH"
WORKDIR /app

# Copy project definition and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install OntoPrune and create symlink in /usr/bin for universal PATH availability
RUN pip install --no-cache-dir . && \
    if [ -f /usr/local/bin/ontoprune-mcp ]; then ln -sf /usr/local/bin/ontoprune-mcp /usr/bin/ontoprune-mcp; fi

# Default entrypoint for stdio MCP
ENTRYPOINT ["python3", "-m", "ontoprune.server"]
