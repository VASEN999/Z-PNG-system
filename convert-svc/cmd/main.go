package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"convert-svc/api"
	"convert-svc/config"
)

func main() {
	// 解析命令行参数
	configPath := flag.String("config", "config/config.yaml", "配置文件路径")
	flag.Parse()

	// 加载配置
	cfg, err := config.Load(*configPath)
	if err != nil {
		log.Fatalf("无法加载配置: %v", err)
	}

	// 初始化HTTP服务器
	server := api.NewServer(cfg)

	// 在独立的goroutine中启动服务
	go func() {
		log.Printf("服务启动在 %s\n", cfg.Server.Address)
		if err := server.Start(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("服务启动失败: %v", err)
		}
	}()

	// 等待中断信号优雅关闭服务器（设置5秒超时）
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("正在关闭服务...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("服务强制关闭: %v", err)
	}

	log.Println("服务已关闭")
} 