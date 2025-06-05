# 构建阶段
FROM golang:1.21-alpine AS builder

WORKDIR /app

# 安装依赖
RUN apk add --no-cache git

# 复制go mod文件
COPY go.mod ./

# 下载所有依赖
RUN go mod download

# 复制源代码
COPY . .

# 构建应用
RUN CGO_ENABLED=0 GOOS=linux go build -o convert-svc ./cmd/main.go

# 运行阶段
FROM ubuntu:22.04

WORKDIR /app

# 安装必要的依赖
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libreoffice \
    imagemagick \
    fonts-noto-cjk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段拷贝编译好的可执行文件
COPY --from=builder /app/convert-svc /app/
COPY --from=builder /app/config/config.yaml /app/config/

# 创建存储目录
RUN mkdir -p /app/storage/uploads /app/storage/converted /app/storage/archive

# 暴露端口
EXPOSE 8080

# 运行
CMD ["/app/convert-svc"] 