package converter

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// ConvertImageToPNG 将图片转换为PNG格式
func ConvertImageToPNG(imagePath, outputDir string) (string, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return "", fmt.Errorf("创建输出目录失败: %w", err)
	}

	// 获取文件名（不含扩展名）
	baseName := filepath.Base(imagePath)
	baseName = strings.TrimSuffix(baseName, filepath.Ext(baseName))
	outputPNG := filepath.Join(outputDir, baseName+".png")

	// 使用ImageMagick转换图片
	// 需要安装ImageMagick: sudo apt-get install imagemagick
	cmd := exec.Command(
		"convert",
		imagePath,
		outputPNG,
	)

	// 执行命令
	if output, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("图片转PNG失败: %w, 输出: %s", err, string(output))
	}

	// 检查转换后的文件是否存在
	if _, err := os.Stat(outputPNG); os.IsNotExist(err) {
		return "", fmt.Errorf("转换后的PNG文件不存在: %s", outputPNG)
	}

	return outputPNG, nil
} 