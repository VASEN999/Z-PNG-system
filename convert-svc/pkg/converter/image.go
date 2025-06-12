package converter

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"convert-svc/pkg/utils"
)

// ConvertImageToPNG 将图片转换为PNG格式
func ConvertImageToPNG(imagePath, outputDir string, sourceID, parentID string) (string, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return "", fmt.Errorf("创建输出目录失败: %w", err)
	}

	// 获取文件名（不含扩展名）
	baseName := filepath.Base(imagePath)
	baseName = strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// 提取订单号（从输出目录路径中）
	var orderID string
	dirParts := strings.Split(outputDir, string(filepath.Separator))
	if len(dirParts) > 0 {
		orderID = dirParts[len(dirParts)-1]
	}

	// 为源文件生成一个唯一标识符（如果没有提供）
	if sourceID == "" {
		sourceID = utils.GenerateSourceID(imagePath, parentID)
		log.Printf("为文件 %s 生成唯一ID: %s", filepath.Base(imagePath), sourceID)
	}

	// 创建临时输出文件名
	tmpOutputPNG := filepath.Join(outputDir, "tmp_"+baseName+".png")

	// 使用ImageMagick转换图片
	// 需要安装ImageMagick: sudo apt-get install imagemagick
	cmd := exec.Command(
		"convert",
		imagePath,
		tmpOutputPNG,
	)

	// 执行命令
	if output, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("图片转PNG失败: %w, 输出: %s", err, string(output))
	}

	// 检查转换后的文件是否存在
	if _, err := os.Stat(tmpOutputPNG); os.IsNotExist(err) {
		return "", fmt.Errorf("转换后的PNG文件不存在: %s", tmpOutputPNG)
	}

	// 简化订单号
	shortOrderID := utils.SimplifyOrderID(orderID)

	// 修改为直接使用sourceID作为文件名的一部分
	// 新格式：订单ID-源文件ID-页码.png
	newName := fmt.Sprintf("%s-%s-%d.png", shortOrderID, sourceID, 1)
	newPath := filepath.Join(outputDir, newName)

	log.Printf("转换文件: %s -> %s (ID: %s)", filepath.Base(imagePath), newName, sourceID)

	// 重命名文件
	if err := os.Rename(tmpOutputPNG, newPath); err != nil {
		return "", fmt.Errorf("重命名文件失败 %s -> %s: %w", tmpOutputPNG, newPath, err)
	}

	return newPath, nil
}
