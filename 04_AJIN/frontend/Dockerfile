# v11: Production frontend image — Vite build → nginx alpine
# Multistage. 산출물은 정적 파일이므로 nginx 한 컨테이너로 종결.

FROM node:20-alpine AS build

WORKDIR /app

# 의존성 — package*.json 만 먼저 복사해 layer 캐싱
COPY package*.json ./
RUN npm ci

# 소스 + 빌드
COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# 런타임 — nginx + 정적 dist
FROM nginx:1.27-alpine

# SPA fallback 설정 + gzip 활성화
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 산출물
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
