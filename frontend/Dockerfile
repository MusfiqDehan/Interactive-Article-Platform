# Node 22 (LTS). Next 16 requires >=20.9, but Node 20 went end-of-life in
# April 2026 and stopped receiving security patches.
FROM node:22-alpine AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NOTE: deliberately no NEXT_PUBLIC_* build args.
#
# Those get inlined into the client bundle at build time, which meant one image
# only ever worked for one domain -- a hard blocker for multi-site -- and made
# the runtime `environment:` block silently inert. Configuration is now read at
# runtime by src/lib/env.server.ts and handed to the browser through
# RuntimeConfigProvider, so a single image serves any tenant.
#
# The build calls the API for generateStaticParams; if it is unreachable the
# helpers fall back to an empty list and pages render on demand instead.
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3003
ENV PORT=3003
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
