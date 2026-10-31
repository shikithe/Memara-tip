FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY kvoter/kvoter.py kvoter/the_odds_api.py kvoter/team_identity.py kvoter/team_aliases.json /app/
USER 65532:65532
ENTRYPOINT ["python","/app/the_odds_api.py"]
