FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system studyroom && useradd --system --gid studyroom studyroom

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=studyroom:studyroom . .
RUN mkdir -p media staticfiles && chown studyroom:studyroom media staticfiles

USER studyroom

CMD ["./start.sh"]
