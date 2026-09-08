FROM python:3.12-slim

RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/factory-venv
WORKDIR /workspace
COPY . .
RUN uv sync --dev
RUN chmod -R a+rwX /opt/factory-venv

CMD ["uv", "run", "python", "-m", "{{ package_name }}"]
