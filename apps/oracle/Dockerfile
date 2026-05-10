FROM node:20-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

FROM base AS builder
WORKDIR /app
COPY . .
RUN pnpm install --frozen-lockfile
WORKDIR /app/apps/oracle
RUN pnpm dlx prisma generate
WORKDIR /app
RUN pnpm build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
# Copy standalone output and static files
COPY --from=builder /app/apps/oracle/.next/standalone ./
COPY --from=builder /app/apps/oracle/.next/static ./apps/oracle/.next/static
COPY --from=builder /app/apps/oracle/public ./apps/oracle/public
# Copy Prisma schema for runtime migrations
COPY --from=builder /app/apps/oracle/prisma ./apps/oracle/prisma

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/oracle/server.js"]
