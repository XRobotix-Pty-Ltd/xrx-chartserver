ARG BASE_TAG=1
FROM xrobotix/xrx-chartserver:BASE_${BASE_TAG}

WORKDIR /app

# --- Python dependencies ---
COPY api/requirements.txt api/requirements.txt
RUN pip3 install --no-cache-dir -r api/requirements.txt

# --- Node.js dependencies ---
COPY renderer/package*.json renderer/
RUN cd renderer && npm ci --omit=dev

# --- Application code ---
COPY api/ api/
COPY renderer/ renderer/
COPY supervisord.conf supervisord.conf

# Build metadata (injected by CI)
ARG CI_COMMIT_BRANCH=local
ARG CI_COMMIT_SHA=unknown
ARG CI_COMMIT_AUTHOR=unknown
ARG CI_COMMIT_MESSAGE=unknown
ARG CI_COMMIT_TIMESTAMP=unknown
ENV CI_COMMIT_BRANCH=${CI_COMMIT_BRANCH}
ENV CI_COMMIT_SHA=${CI_COMMIT_SHA}

EXPOSE 8000

CMD ["supervisord", "-c", "/app/supervisord.conf"]
