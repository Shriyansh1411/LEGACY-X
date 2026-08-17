FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
# Remove package-lock to avoid locked optional native binaries, set mirror, then install
RUN rm -f package-lock.json && npm config set registry https://registry.npmmirror.com/ && npm install --no-optional

COPY . .
# Try to add the optional native rollup binary into node_modules so rollup's
# runtime check finds it on ARM platforms. If the package isn't available,
# continue (build may still fail and will provide useful logs).
RUN npm install @rollup/rollup-linux-arm64-musl --no-save || true
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
