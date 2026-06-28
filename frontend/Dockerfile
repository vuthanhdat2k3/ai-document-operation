# =============================================================================
# AI Document Operations Agent - Frontend Dockerfile (multi-stage)
# =============================================================================

FROM node:20-alpine AS base
WORKDIR /app

# --- Development stage ---
FROM base AS development
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
# Install deps at runtime to stay in sync with bind-mounted package.json
CMD ["sh", "-c", "npm install && npm run dev"]

# --- Build stage ---
FROM base AS builder
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Production stage ---
FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 --ingroup nodejs nextjs
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
