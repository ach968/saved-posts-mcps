FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

# Install Python 3.13 from deadsnakes PPA
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.13 python3.13-venv python3.13-dev && \
    rm -rf /var/lib/apt/lists/*

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

# Install the package using Python 3.13
RUN uv pip install --python python3.13 --system .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8002

# Expose port for HTTP transport
EXPOSE 8002

# Run the MCP server using Python 3.13
CMD ["python3.13", "-m", "src.reddit.server"]
