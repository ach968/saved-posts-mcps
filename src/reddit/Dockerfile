FROM python:3.13-slim

WORKDIR /app

# Install uv for faster dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY README.md .

# Create src directory structure and install dependencies
RUN mkdir -p src/common src/x src/reddit
COPY src/__init__.py src/
COPY src/common/ src/common/
COPY src/reddit/ src/reddit/

# Create placeholder for x to satisfy imports
RUN touch src/x/__init__.py

# Install the package
RUN uv pip install --system .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8002

# Expose port for HTTP transport
EXPOSE 8002

# Run the MCP server
CMD ["python", "-m", "src.reddit.server"]
