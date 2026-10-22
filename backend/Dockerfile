FROM python:3.10-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS runtime

COPY app.py ./

EXPOSE 5000

ENTRYPOINT ["python", "app.py"]

FROM dependencies AS test

COPY app.py test_app.py ./
RUN mkdir -p /reports

CMD ["pytest", "-q", "--cov=app", "--cov-report=xml:/reports/coverage.xml", "--junitxml=/reports/xunit.xml", "test_app.py"]
