FROM python:3.13-slim

LABEL org.opencontainers.image.title="mcp-diary"
LABEL org.opencontainers.image.description="MCP diary for human and AI: separate encrypted private zones plus a shared zone, enforced in code"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/

RUN pip install --no-cache-dir .

# 数据目录（三个 SQLite 库与密钥）默认放 /app/data，容器里用卷挂载覆盖
ENV DIARY_DATA_DIR=/app/data
RUN mkdir -p /app/data

# MCP stdio server 不监听端口，由宿主 MCP 客户端拉起或 compose 内部使用
ENTRYPOINT ["mcp-diary-server"]
