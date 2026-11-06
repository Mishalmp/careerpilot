# CareerPilot web image. Build from the repository root:
#   docker build -f docker/web.Dockerfile -t careerpilot-web apps/web
# API_ORIGIN and RUNNER_ORIGINS are baked in at build time (Next.js reads them into its route table).
FROM node:22-slim

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# Dependencies first so they are cached. The postinstall script copies the in-browser Python and SQL
# runtimes into public/ (about 30 MB).
COPY package.json package-lock.json ./
COPY scripts ./scripts
RUN npm ci

COPY . .
ARG API_ORIGIN=http://api:8010
ARG RUNNER_ORIGINS=http://localhost:3100,http://127.0.0.1:3100
ENV API_ORIGIN=${API_ORIGIN} RUNNER_ORIGINS=${RUNNER_ORIGINS}
RUN npm run build && chown -R node:node /app

USER node
EXPOSE 3100
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:3100/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["npx", "next", "start", "-p", "3100"]
