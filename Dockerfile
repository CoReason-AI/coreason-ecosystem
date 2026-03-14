# Stage 1: Builder
FROM python:3.14-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy the project files
COPY pyproject.toml .
COPY uv.lock .
COPY src/ ./src/
COPY README.md .
COPY LICENSE .

# Install dependencies and build the wheel
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# Build the execution plane wheel
RUN uv build --wheel --out-dir /wheels


# Stage 2: Runtime
FROM python:3.14-slim AS runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Add user's local bin to PATH
ENV PATH="/home/appuser/app/.venv/bin:/home/appuser/.local/bin:${PATH}"

WORKDIR /home/appuser/app

# Copy ONLY the wheel from builder
COPY --from=builder /wheels /wheels

# Create a fresh, empty production venv and install the wheel
RUN uv venv /home/appuser/app/.venv && \
    uv pip install --no-cache /wheels/*.whl

CMD ["coreason"]
