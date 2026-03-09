FROM python:3.9-slim

# 安装编译工具和依赖
RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt uwsgi

COPY . .

EXPOSE 5000

CMD ["uwsgi", "--http", ":5000", "--wsgi-file", "beihuo_system.py", "--callable", "app", "--processes", "4", "--threads", "2", "--master"]