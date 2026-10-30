# MemaraSix AI Lab (isolated research)

This is an independent, non-production workspace. It does not start or modify the MemaraSix website, tickets, bankroll or publishing workflows.

## Safety boundaries
- Develop only on the feature branch; never merge to main without review.
- No production secrets, deployment tokens, repository write credentials or live publication actions.
- No mounting the production repository or data directories as writable volumes.
- Research outputs must be stored in lab-specific paths and never imported automatically by production.
- OpenAI API integration, ESPN/statistics enrichment, odds reconciliation, calibration and tests are future modules; they are NOT implemented by this scaffold.

## Local smoke test
From repository root: `docker build -f ai-lab/Dockerfile -t memarasix-ai-lab .` then `docker run --rm --network none --read-only --tmpfs /tmp memarasix-ai-lab`.

The initial container only syntax-checks its isolated Python files; it does not run sports collectors. The existing C research workflow remains separate and unchanged.
