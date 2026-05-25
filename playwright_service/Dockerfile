FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY playwright_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY playwright_service/ ./playwright_service/
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "playwright_service.main"]
