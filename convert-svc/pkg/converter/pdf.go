package converter

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// ConvertPDFToPNG 将PDF文件转换为PNG图片
func ConvertPDFToPNG(pdfPath, outputDir string, dpi int) ([]string, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, fmt.Errorf("创建输出目录失败: %w", err)
	}

	// 获取文件名（不含扩展名）
	baseName := filepath.Base(pdfPath)
	baseName = strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// 使用pdftoppm命令行工具将PDF转换为PNG
	// 需要安装poppler-utils: sudo apt-get install poppler-utils
	cmd := exec.Command(
		"pdftoppm",
		"-png",
		"-r", strconv.Itoa(dpi), // 设置DPI
		pdfPath,
		filepath.Join(outputDir, baseName),
	)

	// 执行命令
	if output, err := cmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("PDF转PNG失败: %w, 输出: %s", err, string(output))
	}

	// 查找生成的文件
	pattern := filepath.Join(outputDir, fmt.Sprintf("%s-*.png", baseName))
	matches, err := filepath.Glob(pattern)
	if err != nil {
		return nil, fmt.Errorf("查找生成的PNG文件失败: %w", err)
	}

	// 如果没有找到文件，可能是单页PDF，检查不带页码的文件
	if len(matches) == 0 {
		singlePattern := filepath.Join(outputDir, fmt.Sprintf("%s.png", baseName))
		singleMatches, err := filepath.Glob(singlePattern)
		if err != nil {
			return nil, fmt.Errorf("查找生成的单页PNG文件失败: %w", err)
		}
		matches = singleMatches
	}

	return matches, nil
} 