FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /lab
RUN useradd --create-home --uid 10001 lab
COPY ai-lab/ /lab/
USER lab
CMD ["python","-m","compileall","-q","/lab"]
