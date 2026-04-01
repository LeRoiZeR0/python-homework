# 第一阶段：基础镜像
# 使用 python:slim 变体，它比 alpine 兼容性更好，比完整版 python 小很多
FROM python:3.11-slim

# 镜像维护者信息 (可选)
LABEL maintainer="chris2funk@gmail.com"

# 设置环境变量
# PYTHONDONTWRITEBYTECODE: 不生成 .pyc 文件
# PYTHONUNBUFFERED: 输出直接发送到终端，不缓存 (方便看日志)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 设置工作目录 (容器内的路径)
# 之后的所有命令都在此目录下执行
WORKDIR /app

# 安装系统级依赖 (pymysql 等可能需要)
# slim 镜像非常精简，有时需要安装 gcc 或 libmariadb-dev
# 这里使用 --no-install-recommends 来减小镜像体积
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 【缓存优化层】
# 先只复制 requirements.txt
# 只要 requirements.txt 不变，Docker 就会复用这一层的缓存，不用每次都重新下载所有 pip 包
COPY requirements.txt .

# 安装 Python 依赖
# 使用 --no-cache-dir 减少镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目的其余代码
# 注意：.dockerignore 会排除 venv, .git, __pycache__ 等
COPY . .

# 容器启动命令
# 因为这是一个常驻的定时任务脚本，直接运行 python main.py
CMD ["python", "main.py"]