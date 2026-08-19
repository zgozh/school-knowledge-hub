# 前端双段构建：node 构建产物 → nginx 静态托管 + 后端反代
# 注：pnpm@11 需要 Node ≥22.13（node:sqlite 内建模块），故用 node:22-alpine
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm@11 --registry=https://registry.npmmirror.com \
    && pnpm install --frozen-lockfile --registry=https://registry.npmmirror.com
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
