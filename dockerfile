
FROM python:3.13.5-slim

WORKDIR /web

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "old_app.py"]