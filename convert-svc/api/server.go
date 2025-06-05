package api

import (
	"context"
	"convert-svc/config"
	"convert-svc/pkg/converter"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// Server HTTP服务器结构体
type Server struct {
	router *gin.Engine
	config *config.Config
	httpServer *http.Server
}

// NewServer 创建一个新的服务器实例
func NewServer(cfg *config.Config) *Server {
	// 设置Gin模式
	if cfg.Server.Mode == "release" {
		gin.SetMode(gin.ReleaseMode)
	} else {
		gin.SetMode(gin.DebugMode)
	}

	// 创建Gin路由器
	r := gin.Default()

	// 创建服务器
	server := &Server{
		router: r,
		config: cfg,
	}

	// 确保存储目录存在
	os.MkdirAll(cfg.Storage.UploadDir, 0755)
	os.MkdirAll(cfg.Storage.ConvertedDir, 0755)
	os.MkdirAll(cfg.Storage.ArchiveDir, 0755)

	// 设置路由
	server.setupRoutes()

	return server
}

// 设置API路由
func (s *Server) setupRoutes() {
	// API群组
	api := s.router.Group("/api")
	{
		// 健康检查
		api.GET("/health", s.healthCheck)
		
		// 文件转换API
		api.POST("/convert", s.convertFile)
		
		// 批量转换API
		api.POST("/convert-batch", s.convertBatch)
	}

	// 静态文件服务（可选）
	s.router.Static("/files", s.config.Storage.ConvertedDir)
}

// Start 启动HTTP服务器
func (s *Server) Start() error {
	// 创建HTTP服务器
	s.httpServer = &http.Server{
		Addr:    s.config.Server.Address,
		Handler: s.router,
	}
	
	// 启动服务器
	return s.httpServer.ListenAndServe()
}

// Shutdown 关闭HTTP服务器
func (s *Server) Shutdown(ctx context.Context) error {
	if s.httpServer != nil {
		return s.httpServer.Shutdown(ctx)
	}
	return nil
}

// 健康检查处理程序
func (s *Server) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "ok",
		"service": "convert-svc",
	})
}

// FileConvertRequest 文件转换请求结构体
type FileConvertRequest struct {
	FilePath string `json:"file_path" binding:"required"` // 文件路径
	OutputDir string `json:"output_dir,omitempty"`        // 可选的输出目录
	DPI int `json:"dpi,omitempty"`                        // 可选的DPI设置
}

// FileConvertResponse 文件转换响应结构体
type FileConvertResponse struct {
	Success bool     `json:"success"`
	Message string   `json:"message"`
	Files   []string `json:"files,omitempty"`
	Error   string   `json:"error,omitempty"`
}

// convertFile 单个文件转换处理程序
func (s *Server) convertFile(c *gin.Context) {
	var req FileConvertRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, FileConvertResponse{
			Success: false,
			Message: "请求格式错误",
			Error:   err.Error(),
		})
		return
	}

	// 检查文件是否存在
	if _, err := os.Stat(req.FilePath); os.IsNotExist(err) {
		c.JSON(http.StatusNotFound, FileConvertResponse{
			Success: false,
			Message: "文件不存在",
			Error:   err.Error(),
		})
		return
	}

	// 确定输出目录
	outputDir := req.OutputDir
	if outputDir == "" {
		outputDir = s.config.Storage.ConvertedDir
	}

	// 确定DPI
	dpi := req.DPI
	if dpi == 0 {
		dpi = s.config.Conversion.DPI
	}

	// 根据文件扩展名进行转换
	ext := strings.ToLower(filepath.Ext(req.FilePath))
	var convertedFiles []string
	var err error

	switch {
	case ext == ".pdf":
		convertedFiles, err = converter.ConvertPDFToPNG(req.FilePath, outputDir, dpi)
	case ext == ".docx" || ext == ".doc":
		convertedFiles, err = converter.ConvertDocxToPNG(req.FilePath, outputDir, dpi)
	case ext == ".pptx" || ext == ".ppt":
		convertedFiles, err = converter.ConvertPptxToPNG(req.FilePath, outputDir, dpi)
	case ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".gif" || ext == ".bmp":
		file, err := converter.ConvertImageToPNG(req.FilePath, outputDir)
		if err == nil {
			convertedFiles = []string{file}
		}
	default:
		c.JSON(http.StatusBadRequest, FileConvertResponse{
			Success: false,
			Message: "不支持的文件类型",
			Error:   fmt.Sprintf("不支持的文件扩展名: %s", ext),
		})
		return
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, FileConvertResponse{
			Success: false,
			Message: "文件转换失败",
			Error:   err.Error(),
		})
		return
	}

	// 如果配置指定删除原始文件
	if s.config.Conversion.DeleteOriginal {
		os.Remove(req.FilePath)
	}

	c.JSON(http.StatusOK, FileConvertResponse{
		Success: true,
		Message: "文件转换成功",
		Files:   convertedFiles,
	})
}

// BatchConvertRequest 批量文件转换请求
type BatchConvertRequest struct {
	Files []FileConvertRequest `json:"files" binding:"required"`
}

// BatchConvertResponse 批量文件转换响应
type BatchConvertResponse struct {
	Success  bool                   `json:"success"`
	Message  string                 `json:"message"`
	Results  map[string]interface{} `json:"results"`
	ErrorMsg string                 `json:"error,omitempty"`
}

// convertBatch 批量文件转换处理程序
func (s *Server) convertBatch(c *gin.Context) {
	var req BatchConvertRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, BatchConvertResponse{
			Success: false,
			Message: "请求格式错误",
			ErrorMsg: err.Error(),
		})
		return
	}

	results := make(map[string]interface{})
	anyErrors := false

	// 为批处理生成一个唯一ID，用于分组文件
	batchID := uuid.New().String()
	batchDir := filepath.Join(s.config.Storage.ConvertedDir, batchID)
	os.MkdirAll(batchDir, 0755)

	for _, fileReq := range req.Files {
		// 设置默认输出目录为批处理目录
		if fileReq.OutputDir == "" {
			fileReq.OutputDir = batchDir
		}

		// 设置默认DPI
		if fileReq.DPI == 0 {
			fileReq.DPI = s.config.Conversion.DPI
		}

		// 处理单个文件
		var convertedFiles []string
		var err error

		// 检查文件是否存在
		if _, err := os.Stat(fileReq.FilePath); os.IsNotExist(err) {
			results[fileReq.FilePath] = map[string]interface{}{
				"success": false,
				"error":   "文件不存在",
			}
			anyErrors = true
			continue
		}

		// 根据文件扩展名进行转换
		ext := strings.ToLower(filepath.Ext(fileReq.FilePath))
		switch {
		case ext == ".pdf":
			convertedFiles, err = converter.ConvertPDFToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI)
		case ext == ".docx" || ext == ".doc":
			convertedFiles, err = converter.ConvertDocxToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI)
		case ext == ".pptx" || ext == ".ppt":
			convertedFiles, err = converter.ConvertPptxToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI)
		case ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".gif" || ext == ".bmp":
			file, err := converter.ConvertImageToPNG(fileReq.FilePath, fileReq.OutputDir)
			if err == nil {
				convertedFiles = []string{file}
			}
		default:
			results[fileReq.FilePath] = map[string]interface{}{
				"success": false,
				"error":   fmt.Sprintf("不支持的文件扩展名: %s", ext),
			}
			anyErrors = true
			continue
		}

		if err != nil {
			results[fileReq.FilePath] = map[string]interface{}{
				"success": false,
				"error":   err.Error(),
			}
			anyErrors = true
		} else {
			results[fileReq.FilePath] = map[string]interface{}{
				"success": true,
				"files":   convertedFiles,
			}

			// 如果配置指定删除原始文件
			if s.config.Conversion.DeleteOriginal {
				os.Remove(fileReq.FilePath)
			}
		}
	}

	c.JSON(http.StatusOK, BatchConvertResponse{
		Success: !anyErrors,
		Message: "批量转换完成",
		Results: results,
	})
} 