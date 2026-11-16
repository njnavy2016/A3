# ============================================================
# Frontend (Vue 3 + Vite) Dockerfile
# 多阶段构建：Node 编译 → Nginx 托管
# ============================================================

# ---- 阶段 1: 编译 ----
FROM node:20-alpine AS builder

WORKDIR /build

COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build

# ---- 阶段 2: Nginx 托管 ----
FROM nginx:alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/ > /dev/null || exit 1
