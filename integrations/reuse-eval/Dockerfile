# The SkillEvaluator task image (Airflow at the parent of apache/airflow#70517,
# full blob-less history, test venv in /opt/afvenv) plus Claude Code, so the
# agent runs headless inside the container rather than on the host.
ARG BASE=catalogify-eval-airflow:base
FROM ${BASE}

ARG CLAUDE_CODE_VERSION=2.1.318
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}" \
 && /root/.local/bin/claude --version
ENV PATH="/root/.local/bin:${PATH}" \
    IS_SANDBOX=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# This branch's catalogify, built into wheel/ by run.py, so `catalogify find`
# exists before the version is published. Trial arms that don't mention it
# never learn it is there.
COPY wheel/ /tmp/catalogify-wheel/
RUN pip install --no-cache-dir /tmp/catalogify-wheel/*.whl && catalogify --version
