# Generated for Glama & Containerized MCP environments
FROM python:3.12-slim

WORKDIR /app

# Copy project definition and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install OntoPrune package and its dependencies
RUN pip install --no-cache-dir .

# Default stdio entrypoint for MCP
ENTRYPOINT ["ontoprune-mcp"]
