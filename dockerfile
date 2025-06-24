FROM python:3.10-slim

WORKDIR .

COPY . .

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["python", "old_app.py"]



