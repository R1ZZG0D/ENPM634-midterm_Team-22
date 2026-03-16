FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV DB_PATH=/app/database/enpm634_midterm_team22.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/app/static/uploads /opt \
    && echo "ENPM634{full_chain_rce}" > /opt/flag.txt

EXPOSE 5000

CMD ["sh", "-c", "python -c 'from app.database import init_database; init_database()' && python -m app.app"]
