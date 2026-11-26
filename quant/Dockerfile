# syntax=docker/dockerfile:1.7
# quant（A 股量化平台）生产镜像：单容器同时提供 API 与前端静态页。
# 数据目录与监听端口全部通过环境变量注入，宿主机路径不会写进镜像。

# ---------- 阶段一：构建前端 ----------
FROM node:20.11-alpine AS web-build
WORKDIR /web
# 依赖清单先落一层：只改业务代码时不必重装 node_modules
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- 阶段二：运行时 ----------
FROM python:3.11-slim-bookworm AS runtime

# 默认值与 compose 的挂载点保持一致；宿主侧用 environment / -e 覆盖即可
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    QUANT_CONFIG=/app/config/config.toml \
    QUANT_HOST=0.0.0.0 \
    QUANT_PORT=8000 \
    QUANT_RAW_DIR=/data/raw \
    QUANT_PARQUET_DIR=/data/parquet \
    QUANT_META_DIR=/data/meta

# zoneinfo 需要系统时区库；pyarrow / duckdb / pandas 均用 manylinux wheel，不需要编译工具链
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# 目录层级必须与仓库一致：PROJECT_ROOT 由 app/config.py 向上三级得到，
# 即 /app/backend/app/config.py -> /app，配置与 web/dist 才落在预期位置
WORKDIR /app/backend

# 只装 pyproject 里的运行时依赖（项目本身不安装，用 python -m app 直接跑），依赖清单仍只有一份
COPY backend/pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# 后端代码 + 前端产物 + 镜像内默认配置（本地 config.toml 含宿主机绝对路径，不进镜像）
COPY backend/app ./app
COPY --from=web-build /web/dist /app/web/dist
COPY config/config.example.toml /app/config/config.toml

# 非 root 运行；数据目录预先建好并授权，命名卷首次挂载时会继承这份属主
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/raw /data/parquet /data/meta \
    && chown -R app:app /app /data
USER app

VOLUME ["/data/raw", "/data/parquet", "/data/meta"]
EXPOSE 8000

# 端口跟着 QUANT_PORT 走，避免改了端口健康检查还打 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health' % os.environ.get('QUANT_PORT','8000'), timeout=3)"

# 监听地址/端口、数据目录都来自配置 + 环境变量，不在命令行重复传参
CMD ["python", "-m", "app"]
