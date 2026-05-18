# syntax=docker/dockerfile:1

# ---- Build stage: compile the React app ----
FROM node:22-alpine AS build
WORKDIR /app

# Reproducible install from the committed lockfile.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Serve stage: nginx serving the static build + reverse proxy ----
FROM nginx:1.27-alpine

# Replace the default site with our SPA + API/admin proxy config.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# The compiled SPA.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
