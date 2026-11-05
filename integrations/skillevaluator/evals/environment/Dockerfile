FROM python:3.12-slim

# Apache Airflow at the parent of apache/airflow#70517 ("Support a Unix Domain
# Socket for the metrics clients"), the feature the contextual case asks for.
#
# A blob-less partial clone keeps the full commit history (catalogify needs it;
# a shallow clone breaks history mining) at about 180 MB. Older file contents
# are fetched from origin on demand, so the container needs network access.
# The merge commit itself is not fetched; the grader fetches its tests after
# the agent has finished.

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# uv gives the agent `uvx catalogify@<version>`, the skill's documented path when
# the CLI is not installed. catalogify itself is deliberately not preinstalled,
# so the baseline arm has no trace of it.
RUN pip install --no-cache-dir uv==0.6.16

ARG AIRFLOW_BASE=f44bb16d825edcb533b5819c152c4d6a23a0ffd9
RUN git init -q /workspace/airflow \
 && cd /workspace/airflow \
 && git remote add origin https://github.com/apache/airflow.git \
 && git fetch -q --filter=blob:none origin "$AIRFLOW_BASE" \
 && git checkout -q -b main FETCH_HEAD \
 && git config user.name "eval" \
 && git config user.email "eval@example.invalid"

# Test environment for the metrics code, installed editable so the agent's
# changes are what the tests import.
RUN uv venv -q -p 3.12 /opt/afvenv \
 && cd /workspace/airflow \
 && VIRTUAL_ENV=/opt/afvenv uv pip install -q \
      -e './shared/observability[all]' -e ./devel-common -e ./airflow-core -e ./task-sdk

# Not on PATH: SkillEvaluator installs its own grader dependencies with
# `python -m pip`, and this uv-made venv has no pip. The prompt names it instead.
ENV AIRFLOW_HOME=/tmp/airflow-home
WORKDIR /workspace/airflow
