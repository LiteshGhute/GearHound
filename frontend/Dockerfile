# --- build stage -----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* env vars into the built JS at build time, not at
# container start, so this has to be a build ARG, not a runtime ENV. Default
# assumes the backend's port is published to the host as-is (the common
# case: `docker compose up` and open the browser on the same machine).
ARG VITE_BACKEND_URL=http://localhost:4000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

# --- serve stage -------------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
