FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --dev

CMD ["uv", "run", "python", "-m", "{{ package_name }}"]
