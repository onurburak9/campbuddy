FROM mcr.microsoft.com/playwright/python:v1.59.0-noble
# xvfb + x11-utils: the browser runs headed against a virtual display because
# Recreation.gov silently drops logins from headless Chromium. See entrypoint.sh.
RUN apt-get update && apt-get install -y --no-install-recommends tini xvfb x11-utils curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY playwright_service/requirements.txt .
# This base image ships the browsers but not the Python bindings, and marks the
# system interpreter as externally managed.
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY playwright_service/ ./playwright_service/
RUN chmod +x ./playwright_service/entrypoint.sh
ENV DISPLAY=:99
# Deliberately NOT `tini -g`: signalling the whole process group SIGTERMs
# Chromium out from under the driver, and playwright.stop() then blocks
# forever. Signal uvicorn alone and let its shutdown hook stop Playwright,
# which reaps the browser processes in-order.
ENTRYPOINT ["tini", "--", "/app/playwright_service/entrypoint.sh"]
CMD ["python", "-m", "playwright_service.main"]
