package converter

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"convert-svc/pkg/utils"
)

// ConvertPDFToPNG 将PDF文件转换为PNG图片
func ConvertPDFToPNG(pdfPath, outputDir string, dpi int, sourceID, parentID string) ([]string, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, fmt.Errorf("创建输出目录失败: %w", err)
	}

	// 获取文件名（不含扩展名）和订单号
	baseName := filepath.Base(pdfPath)
	baseName = strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// 提取订单号（从输出目录路径中）
	var orderID string
	dirParts := strings.Split(outputDir, string(filepath.Separator))
	if len(dirParts) > 0 {
		orderID = dirParts[len(dirParts)-1]
	}

	// 为源文件生成一个唯一标识符（如果没有提供）
	if sourceID == "" {
		sourceID = utils.GenerateSourceID(pdfPath, parentID)
		log.Printf("为PDF文件 %s 生成唯一ID: %s", filepath.Base(pdfPath), sourceID)
	}

	// 创建临时输出前缀（使用pdftoppm时需要）
	tmpPrefix := filepath.Join(outputDir, "tmp_convert")

	// 使用pdftoppm命令行工具将PDF转换为PNG
	// 需要安装poppler-utils: sudo apt-get install poppler-utils
	cmd := exec.Command(
		"pdftoppm",
		"-png",
		"-r", strconv.Itoa(dpi), // 设置DPI
		pdfPath,
		tmpPrefix,
	)

	// 执行命令
	if output, err := cmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("PDF转PNG失败: %w, 输出: %s", err, string(output))
	}

	// 查找生成的临时文件
	pattern := filepath.Join(outputDir, "tmp_convert-*.png")
	tmpFiles, err := filepath.Glob(pattern)
	if err != nil {
		return nil, fmt.Errorf("查找生成的PNG文件失败: %w", err)
	}

	// 如果没有找到文件，可能是单页PDF，检查不带页码的文件
	if len(tmpFiles) == 0 {
		singlePattern := filepath.Join(outputDir, "tmp_convert.png")
		singleMatches, err := filepath.Glob(singlePattern)
		if err != nil {
			return nil, fmt.Errorf("查找生成的单页PNG文件失败: %w", err)
		}
		tmpFiles = singleMatches
	}

	// 简化订单号
	shortOrderID := utils.SimplifyOrderID(orderID)

	log.Printf("转换PDF: %s 生成 %d 个图片文件，使用哈希ID: %s",
		filepath.Base(pdfPath), len(tmpFiles), sourceID)

	// 重命名文件为新格式：订单ID-源文件哈希-页码.png
	resultFiles := make([]string, 0, len(tmpFiles))
	for i, tmpFile := range tmpFiles {
		// 新的文件名格式：订单ID-源文件哈希-页码.png
		newName := fmt.Sprintf("%s-%s-%d.png", shortOrderID, sourceID, i+1)
		newPath := filepath.Join(outputDir, newName)

		log.Printf("重命名转换文件: [%d/%d] %s -> %s",
			i+1, len(tmpFiles), filepath.Base(tmpFile), newName)

		// 重命名文件
		if err := os.Rename(tmpFile, newPath); err != nil {
			return nil, fmt.Errorf("重命名文件失败 %s -> %s: %w", tmpFile, newPath, err)
		}

		resultFiles = append(resultFiles, newPath)
	}

	return resultFiles, nil
}
