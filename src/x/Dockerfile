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

# Create src directory structure
RUN mkdir -p src/common src/x src/reddit
COPY src/__init__.py src/
COPY src/common/ src/common/
COPY src/x/ src/x/

# Create placeholder for reddit to satisfy imports
RUN touch src/reddit/__init__.py

# Install the package using Python 3.13
RUN uv pip install --python python3.13 --system .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port for HTTP transport (if used)
EXPOSE 8000

# Run the MCP server using Python 3.13
CMD ["python3.13", "-m", "src.x.server"]
