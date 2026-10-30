FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY kvoter/kvoter.py /app/kvoter.py
USER 65532:65532
ENTRYPOINT ["python","/app/kvoter.py"]
