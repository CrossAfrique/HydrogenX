# Use Python 3.12 slim base image
FROM python:3.12-slim

# Set environment variables for Cargo and Rustup to writable directories
ENV CARGO_HOME=/app/.cargo
ENV RUSTUP_HOME=/app/.rustup
ENV PATH="/app/.cargo/bin:$PATH"

# Install system dependencies for Rust and Python packages
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Run the application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]