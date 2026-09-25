# ─────────────────────────────────────────────
# OpenNotebook — Frontend Dockerfile
# ─────────────────────────────────────────────

# Stage 1: Build
FROM node:20-slim AS build

WORKDIR /app

# Copy package manifests first (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build production bundle
RUN npm run build

# ─────────────────────────────────────────────
# Stage 2: Serve with Nginx
# ─────────────────────────────────────────────
FROM nginx:alpine AS production

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

ENV PORT=8080

# Expose HTTP port
EXPOSE 8080

# Health check (honors $PORT for Cloud Run; defaults to 8080 elsewhere)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:${PORT:-8080}/ || exit 1

# Start Nginx (honors $PORT and $BACKEND_URL for Cloud Run; defaults to 8080 and opennotebook-api elsewhere)
CMD ["sh", "-c", "sed -i \"s/listen 80;/listen ${PORT:-8080};/g\" /etc/nginx/conf.d/default.conf && TARGET_BACKEND=$(echo \"$BACKEND_URL\" | sed 's|/*$||') && if [ -n \"$TARGET_BACKEND\" ]; then sed -i \"s|http://opennotebook-api:8000|${TARGET_BACKEND}|g\" /etc/nginx/conf.d/default.conf; fi && exec nginx -g 'daemon off;'"]
