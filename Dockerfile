FROM ghcr.io/astral-sh/uv:debian

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync 

EXPOSE 8000

CMD ["uv", "run", "main.py"]

