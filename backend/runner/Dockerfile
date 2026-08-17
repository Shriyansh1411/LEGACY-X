FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /app/requirements.txt
# Runner will execute workspace under /workspace
WORKDIR /workspace
ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["pytest -q"]
