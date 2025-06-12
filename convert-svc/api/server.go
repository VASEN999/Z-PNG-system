package api

import (
	"context"
	"convert-svc/config"
	"convert-svc/pkg/converter"
	"crypto/sha256"
	"encoding/hex"
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
	router     *gin.Engine
	config     *config.Config
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

	// 添加CORS中间件
	r.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Origin, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "Content-Length")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	})

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

		// 文件重命名API
		api.POST("/rename", s.renameFile)
	}

	// 添加根路径健康检查，与启动脚本兼容
	s.router.GET("/health", s.healthCheck)

	// 静态文件服务 - 确保使用正确的路径
	s.router.Static("/files", s.config.Storage.ConvertedDir)

	// 添加文件信息API
	s.router.GET("/file-info/:filename", s.getFileInfo)
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
		"status":  "ok",
		"service": "convert-svc",
	})
}

// FileConvertRequest 文件转换请求结构体
type FileConvertRequest struct {
	FilePath  string `json:"file_path" binding:"required"` // 文件路径
	OutputDir string `json:"output_dir,omitempty"`         // 可选的输出目录
	DPI       int    `json:"dpi,omitempty"`                // 可选的DPI设置
	OrderId   string `json:"order_id,omitempty"`           // 可选的订单ID，用于按订单组织文件
	SourceId  string `json:"source_id,omitempty"`          // 可选的源文件标识符
	ParentId  string `json:"parent_id,omitempty"`          // 可选的父文件标识符
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

	// 打印详细的调试信息
	fileContent, readErr := os.ReadFile(req.FilePath)
	var contentHash string
	if readErr == nil {
		hasher := sha256.New()
		hasher.Write(fileContent)
		contentHash = hex.EncodeToString(hasher.Sum(nil))
		fmt.Printf("文件内容哈希: %s (前6位: %s), 文件路径: %s, 源ID: %s, 父ID: %s\n",
			contentHash, contentHash[:6], req.FilePath, req.SourceId, req.ParentId)
	} else {
		fmt.Printf("无法读取文件内容进行哈希计算: %v\n", readErr)
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
	var outputDir string
	if req.OutputDir != "" {
		outputDir = req.OutputDir
	} else if req.OrderId != "" {
		// 如果提供了订单ID，则在converted目录下创建以订单ID命名的子目录
		outputDir = filepath.Join(s.config.Storage.ConvertedDir, req.OrderId)
		fmt.Printf("使用订单ID创建输出目录: %s\n", outputDir)
	} else {
		outputDir = s.config.Storage.ConvertedDir
	}

	// 确保目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		c.JSON(http.StatusInternalServerError, FileConvertResponse{
			Success: false,
			Message: "创建输出目录失败",
			Error:   err.Error(),
		})
		return
	}

	// 确定DPI
	dpi := req.DPI
	if dpi == 0 {
		dpi = s.config.Conversion.DPI
	}

	// 根据文件扩展名进行转换
	ext := strings.ToLower(filepath.Ext(req.FilePath))
	var convertedFiles []string
	var convErr error

	// 处理源文件标识符(source_id)和父文件标识符(parent_id)
	sourceID := req.SourceId
	parentID := req.ParentId

	// 记录传入的源文件ID
	if sourceID != "" {
		fmt.Printf("使用客户端提供的源文件ID: %s\n", sourceID)
	} else {
		// 如果没有提供源文件ID，使用UUID生成一个而不是使用文件内容
		sourceID = uuid.New().String()[:6]
		fmt.Printf("客户端未提供源文件ID，生成新ID: %s\n", sourceID)
	}

	switch {
	case ext == ".pdf":
		// 传递源文件ID和父ID给转换函数
		convertedFiles, convErr = converter.ConvertPDFToPNG(req.FilePath, outputDir, dpi, sourceID, parentID)
	case ext == ".docx" || ext == ".doc":
		convertedFiles, convErr = converter.ConvertDocxToPNG(req.FilePath, outputDir, dpi, sourceID, parentID)
	case ext == ".pptx" || ext == ".ppt":
		convertedFiles, convErr = converter.ConvertPptxToPNG(req.FilePath, outputDir, dpi, sourceID, parentID)
	case ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".gif" || ext == ".bmp":
		file, imgErr := converter.ConvertImageToPNG(req.FilePath, outputDir, sourceID, parentID)
		if imgErr == nil {
			convertedFiles = []string{file}
		} else {
			convErr = imgErr
		}
	default:
		c.JSON(http.StatusBadRequest, FileConvertResponse{
			Success: false,
			Message: "不支持的文件类型",
			Error:   fmt.Sprintf("不支持的文件扩展名: %s", ext),
		})
		return
	}

	if convErr != nil {
		c.JSON(http.StatusInternalServerError, FileConvertResponse{
			Success: false,
			Message: "文件转换失败",
			Error:   convErr.Error(),
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
	Files   []FileConvertRequest `json:"files" binding:"required"`
	OrderId string               `json:"order_id,omitempty"` // 可选的订单ID，用于按订单组织文件
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
			Success:  false,
			Message:  "请求格式错误",
			ErrorMsg: err.Error(),
		})
		return
	}

	results := make(map[string]interface{})
	anyErrors := false

	// 为批处理生成一个唯一ID，用于分组文件
	batchID := uuid.New().String()

	// 确定输出根目录
	var outputRootDir string
	if req.OrderId != "" {
		// 如果提供了订单ID，则使用它创建子目录
		outputRootDir = filepath.Join(s.config.Storage.ConvertedDir, req.OrderId)
	} else {
		// 否则使用批处理ID作为默认目录名
		outputRootDir = filepath.Join(s.config.Storage.ConvertedDir, batchID)
	}

	// 确保目录存在
	os.MkdirAll(outputRootDir, 0755)

	for _, fileReq := range req.Files {
		// 设置默认输出目录
		if fileReq.OutputDir == "" {
			fileReq.OutputDir = outputRootDir
		}

		// 如果文件请求没有订单ID但批请求有，则继承批请求的订单ID
		if fileReq.OrderId == "" {
			fileReq.OrderId = req.OrderId
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

		// 处理源文件标识符和父文件标识符
		sourceID := fileReq.SourceId
		parentID := fileReq.ParentId

		// 根据文件扩展名进行转换
		ext := strings.ToLower(filepath.Ext(fileReq.FilePath))
		switch {
		case ext == ".pdf":
			convertedFiles, err = converter.ConvertPDFToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI, sourceID, parentID)
		case ext == ".docx" || ext == ".doc":
			convertedFiles, err = converter.ConvertDocxToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI, sourceID, parentID)
		case ext == ".pptx" || ext == ".ppt":
			convertedFiles, err = converter.ConvertPptxToPNG(fileReq.FilePath, fileReq.OutputDir, fileReq.DPI, sourceID, parentID)
		case ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".gif" || ext == ".bmp":
			file, err := converter.ConvertImageToPNG(fileReq.FilePath, fileReq.OutputDir, sourceID, parentID)
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

// FileInfoResponse 文件信息响应结构体
type FileInfoResponse struct {
	Success  bool   `json:"success"`
	Filename string `json:"filename"`
	URL      string `json:"url"`
	MimeType string `json:"mime_type"`
	Size     int64  `json:"size"`
	Error    string `json:"error,omitempty"`
}

// getFileInfo 获取文件信息处理程序
func (s *Server) getFileInfo(c *gin.Context) {
	filename := c.Param("filename")

	// 拼接完整文件路径
	filePath := filepath.Join(s.config.Storage.ConvertedDir, filename)

	// 检查文件是否存在
	fileInfo, err := os.Stat(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			// 如果在根目录没找到，尝试在子目录中查找
			found := false
			err := filepath.Walk(s.config.Storage.ConvertedDir, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return err
				}
				if !info.IsDir() && info.Name() == filename {
					filePath = path
					fileInfo = info
					found = true
					return filepath.SkipAll
				}
				return nil
			})

			if err != nil || !found {
				c.JSON(http.StatusNotFound, FileInfoResponse{
					Success: false,
					Error:   "文件不存在",
				})
				return
			}
		} else {
			c.JSON(http.StatusInternalServerError, FileInfoResponse{
				Success: false,
				Error:   err.Error(),
			})
			return
		}
	}

	// 判断是否是常规文件
	if !fileInfo.Mode().IsRegular() {
		c.JSON(http.StatusBadRequest, FileInfoResponse{
			Success: false,
			Error:   "不是常规文件",
		})
		return
	}

	// 确定MIME类型
	mimeType := "image/png" // 默认类型

	// 获取文件大小
	fileSize := fileInfo.Size()

	// 构建文件URL
	serverAddress := s.config.Server.Address
	if serverAddress[0] == ':' {
		// 如果地址只包含端口号，添加默认主机名
		serverAddress = "http://localhost" + serverAddress
	} else if !strings.HasPrefix(serverAddress, "http") {
		// 如果没有协议前缀，添加http://
		serverAddress = "http://" + serverAddress
	}

	// 获取相对于转换目录的路径
	relPath, err := filepath.Rel(s.config.Storage.ConvertedDir, filePath)
	if err != nil {
		relPath = filename
	}

	// 构建URL
	fileURL := fmt.Sprintf("%s/files/%s", serverAddress, relPath)

	// 返回文件信息
	c.JSON(http.StatusOK, FileInfoResponse{
		Success:  true,
		Filename: filename,
		URL:      fileURL,
		MimeType: mimeType,
		Size:     fileSize,
	})
}

// FileRenameRequest 文件重命名请求结构体
type FileRenameRequest struct {
	OriginalPath string `json:"original_path" binding:"required"` // 原始文件路径（相对于转换目录）
	NewName      string `json:"new_name" binding:"required"`      // 新文件名
	OrderId      string `json:"order_id,omitempty"`               // 可选的订单ID
}

// FileRenameResponse 文件重命名响应结构体
type FileRenameResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	NewPath string `json:"new_path,omitempty"` // 重命名后的相对路径
	NewURL  string `json:"new_url,omitempty"`  // 重命名后的URL
	Error   string `json:"error,omitempty"`
}

// renameFile 文件重命名处理程序
func (s *Server) renameFile(c *gin.Context) {
	var req FileRenameRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, FileRenameResponse{
			Success: false,
			Message: "请求格式错误",
			Error:   err.Error(),
		})
		return
	}

	// 构建完整路径
	originalPath := req.OriginalPath
	if !strings.HasPrefix(originalPath, s.config.Storage.ConvertedDir) {
		// 如果提供的是相对路径，转换为绝对路径
		originalPath = filepath.Join(s.config.Storage.ConvertedDir, originalPath)
	}

	// 检查原始文件是否存在
	if _, err := os.Stat(originalPath); os.IsNotExist(err) {
		c.JSON(http.StatusNotFound, FileRenameResponse{
			Success: false,
			Message: "原始文件不存在",
			Error:   err.Error(),
		})
		return
	}

	// 确定新文件路径
	dir := filepath.Dir(originalPath)
	newPath := filepath.Join(dir, req.NewName)

	// 检查新路径是否已存在 - 修改此处逻辑，不再添加时间戳
	if _, err := os.Stat(newPath); err == nil {
		// 文件已存在，但我们不添加时间戳，而是覆盖它
		// 先删除已存在的文件
		if err := os.Remove(newPath); err != nil {
			c.JSON(http.StatusInternalServerError, FileRenameResponse{
				Success: false,
				Message: "无法删除已存在的文件",
				Error:   err.Error(),
			})
			return
		}
	}

	// 执行重命名
	if err := os.Rename(originalPath, newPath); err != nil {
		c.JSON(http.StatusInternalServerError, FileRenameResponse{
			Success: false,
			Message: "重命名失败",
			Error:   err.Error(),
		})
		return
	}

	// 获取相对路径（用于URL）
	relPath, err := filepath.Rel(s.config.Storage.ConvertedDir, newPath)
	if err != nil {
		relPath = filepath.Base(newPath)
	}

	// 构建新URL
	serverAddress := s.config.Server.Address
	if serverAddress[0] == ':' {
		// 如果地址只包含端口号，添加默认主机名
		serverAddress = "http://localhost" + serverAddress
	} else if !strings.HasPrefix(serverAddress, "http") {
		// 如果没有协议前缀，添加http://
		serverAddress = "http://" + serverAddress
	}

	newURL := fmt.Sprintf("%s/files/%s", serverAddress, relPath)

	// 返回成功响应
	c.JSON(http.StatusOK, FileRenameResponse{
		Success: true,
		Message: "文件重命名成功",
		NewPath: relPath,
		NewURL:  newURL,
	})
}
