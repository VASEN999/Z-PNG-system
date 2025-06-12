package converter

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// ConvertOfficeToPDF 将Office文档（Word，PPT等）转换为PDF
func ConvertOfficeToPDF(officePath, outputDir string) (string, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return "", fmt.Errorf("创建输出目录失败: %w", err)
	}

	// 获取文件名（不含扩展名）
	baseName := filepath.Base(officePath)
	baseName = strings.TrimSuffix(baseName, filepath.Ext(baseName))
	outputPDF := filepath.Join(outputDir, baseName+".pdf")

	// 使用LibreOffice将Office文档转换为PDF
	// 需要安装LibreOffice: sudo apt-get install libreoffice
	cmd := exec.Command(
		"libreoffice",
		"--headless",
		"--convert-to", "pdf",
		"--outdir", outputDir,
		officePath,
	)

	// 执行命令
	if output, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("Office转PDF失败: %w, 输出: %s", err, string(output))
	}

	// 检查生成的PDF文件是否存在
	if _, err := os.Stat(outputPDF); os.IsNotExist(err) {
		return "", fmt.Errorf("转换后的PDF文件不存在: %s", outputPDF)
	}

	return outputPDF, nil
}

// ConvertDocxToPNG 将Word文档转换为PNG图片
func ConvertDocxToPNG(docxPath, outputDir string, dpi int, sourceID, parentID string) ([]string, error) {
	// 先转换为PDF
	pdfPath, err := ConvertOfficeToPDF(docxPath, outputDir)
	if err != nil {
		return nil, fmt.Errorf("Word转PDF失败: %w", err)
	}

	// 然后将PDF转换为PNG
	pngFiles, err := ConvertPDFToPNG(pdfPath, outputDir, dpi, sourceID, parentID)
	if err != nil {
		return nil, fmt.Errorf("PDF转PNG失败: %w", err)
	}

	// 可选：删除中间PDF文件
	// os.Remove(pdfPath)

	return pngFiles, nil
}

// ConvertPptxToPNG 将PPT文档转换为PNG图片
func ConvertPptxToPNG(pptxPath, outputDir string, dpi int, sourceID, parentID string) ([]string, error) {
	// 先转换为PDF
	pdfPath, err := ConvertOfficeToPDF(pptxPath, outputDir)
	if err != nil {
		return nil, fmt.Errorf("PPT转PDF失败: %w", err)
	}

	// 然后将PDF转换为PNG
	pngFiles, err := ConvertPDFToPNG(pdfPath, outputDir, dpi, sourceID, parentID)
	if err != nil {
		return nil, fmt.Errorf("PDF转PNG失败: %w", err)
	}

	// 可选：删除中间PDF文件
	// os.Remove(pdfPath)

	return pngFiles, nil
}
