FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir django djangorestframework gunicorn

EXPOSE 8000
CMD ["gunicorn", "smart_property.wsgi:application", "--bind", "0.0.0.0:8000"]
