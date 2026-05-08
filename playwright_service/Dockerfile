FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY playwright_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY playwright_service/ ./playwright_service/
CMD ["python", "-m", "playwright_service.main"]
