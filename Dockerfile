FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
CMD ["python", "server.py"]
