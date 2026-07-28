FROM python:3.12-slim

# uv をコンテナ内に取り込む（ホストには不要）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# curl は healthcheck 用
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 1) 依存だけ先に入れる（プロジェクト本体はまだ入れない → README.md不要）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    || uv sync --no-dev --no-install-project

# 2) アプリ本体をコピーしてからプロジェクトを入れる
COPY . .
RUN uv sync --frozen --no-dev || uv sync --no-dev

# 名前付きボリュームで config を上書きしても既定を seed できるよう控えを残す
RUN cp -a /app/config /app/config.default \
    && chmod +x /app/docker/entrypoint.sh

# 8501 = Streamlit ダッシュボード / 8502 = 受信API（同一イメージ・compose で使い分け）
EXPOSE 8501 8502

ENV PYTHONPATH=/app/src
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# 既定は dashboard。受信APIは compose 側で command を上書きして起動する。
CMD ["uv", "run", "streamlit", "run", "dashboard/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
