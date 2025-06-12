package utils

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// SimplifyFileName 简化文件名，截取指定长度并只保留字母数字和下划线
// 注意：修改后此函数已不再使用，保留是为了兼容旧代码
func SimplifyFileName(name string, maxLength int) string {
	// 检查是否包含非ASCII字符（如中文）
	hasNonASCII := false

	for _, r := range name {
		if r > 127 { // 非ASCII字符
			hasNonASCII = true
			break
		}
	}

	// 如果有非ASCII字符（如中文），使用英文前缀代替
	if hasNonASCII {
		// 基本前缀
		result := "doc"

		// 检查是否有形如 _0001、_0002 这样的序号尾缀
		seqRegex := regexp.MustCompile(`_0*(\d+)($|\.)`)
		seqMatches := seqRegex.FindStringSubmatch(name)

		if len(seqMatches) >= 2 && seqMatches[1] != "" {
			// 如果找到序号，使用序号作为标识符的一部分
			result += seqMatches[1]
		} else {
			// 否则，提取数字作为标识符
			digits := ""
			for _, r := range name {
				if r >= '0' && r <= '9' {
					digits += string(r)
				}
			}

			// 如果有数字，添加到结果中
			if digits != "" {
				if len(digits) > 5 {
					// 优先使用末尾的数字，这样对于形如 20250529110331175_X 的文件名
					// 可以区分不同的 X 值
					digits = digits[len(digits)-5:]
				}
				result += digits
			}
		}

		// 添加文件名长度的哈希值最后一位，增加唯一性
		hashValue := fmt.Sprintf("%x", len(name))
		result += hashValue[len(hashValue)-1:]

		return result
	}

	// 移除所有特殊字符
	var result strings.Builder
	for _, r := range name {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' {
			result.WriteRune(r)
		}
	}

	// 截取指定长度
	simplified := result.String()
	if len(simplified) > maxLength {
		simplified = simplified[:maxLength]
	}

	return simplified
}

// SimplifyOrderID 简化订单ID
func SimplifyOrderID(orderID string) string {
	// 如果订单ID形如"20250609-fca939e7"，只保留"fca939e7"部分
	parts := strings.Split(orderID, "-")
	if len(parts) >= 2 && len(parts[1]) >= 6 {
		return parts[1][:6] // 取短ID的前6位
	}

	// 如果订单ID太长，只保留前8位
	if len(orderID) > 8 {
		return orderID[:8]
	}

	return orderID
}

// ComputeFileHash 计算文件的SHA-256哈希值
func ComputeFileHash(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("打开文件失败: %w", err)
	}
	defer file.Close()

	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", fmt.Errorf("计算哈希失败: %w", err)
	}

	return hex.EncodeToString(hasher.Sum(nil)), nil
}

// GenerateSourceID 根据文件内容生成短的源文件标识符
// 修改后总是包含文件名中的数字序号（如果有）以确保唯一性
func GenerateSourceID(filePath string, parentID string) string {
	// 使用文件内容哈希值作为唯一标识符的基础
	fileHash, err := ComputeFileHash(filePath)
	if err == nil {
		// 提取文件名中的序号（如果有）
		baseName := filepath.Base(filePath)
		fileName := strings.TrimSuffix(baseName, filepath.Ext(baseName))

		// 检查是否有形如 _0001、_0002 这样的序号尾缀
		seqRegex := regexp.MustCompile(`_0*(\d+)($|\.)`)
		seqMatches := seqRegex.FindStringSubmatch(fileName)

		// 组合哈希值前3位和序号（如果有）
		if len(seqMatches) >= 2 && seqMatches[1] != "" {
			// 如果找到序号，组合哈希和序号
			return fmt.Sprintf("%s-%s", fileHash[:3], seqMatches[1])
		}

		// 成功计算文件哈希值，使用前6个字符
		return fileHash[:6]
	}

	// 如果无法读取文件内容，回退到使用路径哈希
	fmt.Printf("警告: 无法计算文件哈希，回退到使用路径: %v\n", err)
	hasher := sha256.New()

	// 获取文件基本名（不含路径和扩展名）
	baseName := filepath.Base(filePath)
	fileName := strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// 提取完整文件路径、文件名及其长度
	hasher.Write([]byte(filePath))
	hasher.Write([]byte(fileName))
	hasher.Write([]byte(fmt.Sprintf("%d", len(fileName)))) // 添加文件名长度作为额外特征

	// 如果文件名包含下划线，尝试提取序号部分，优先使用序号作为区分
	seq := ""
	if strings.Contains(fileName, "_") {
		parts := strings.Split(fileName, "_")
		if len(parts) > 0 {
			lastPart := parts[len(parts)-1]
			hasher.Write([]byte(lastPart)) // 使用最后一部分作为序号
			seq = lastPart
		}
	}

	// 如果有父标识符，将其加入哈希计算中
	if parentID != "" {
		hasher.Write([]byte(parentID))
	}

	// 获取哈希值的前6个字符作为源文件标识符
	hash := fmt.Sprintf("%x", hasher.Sum(nil))
	if seq != "" {
		// 如果有序号，返回"哈希前缀-序号"格式
		return fmt.Sprintf("%s-%s", hash[:3], seq)
	}
	return hash[:6]
}

// GenerateNestedSourceID 为嵌套文档生成源文件标识符
// zipPath: 压缩包路径
// innerPath: 压缩包内的文件路径
// fileContent: 文件内容
// parentID: 可选的父级ID（用于多层嵌套）
func GenerateNestedSourceID(zipPath string, innerPath string, fileContent []byte, parentID string) string {
	// 如果有文件内容，直接使用内容的哈希值
	if len(fileContent) > 0 {
		hasher := sha256.New()
		hasher.Write(fileContent)

		// 提取内部文件序号（如果有）
		baseName := filepath.Base(innerPath)
		fileName := strings.TrimSuffix(baseName, filepath.Ext(baseName))

		// 检查是否有形如 _0001、_0002 这样的序号尾缀
		seqRegex := regexp.MustCompile(`_0*(\d+)($|\.)`)
		seqMatches := seqRegex.FindStringSubmatch(fileName)

		// 如果有父ID，添加到哈希中以增加唯一性
		if parentID != "" {
			hasher.Write([]byte(parentID))
		}

		hash := hex.EncodeToString(hasher.Sum(nil))

		// 组合哈希值前3位和序号（如果有）
		if len(seqMatches) >= 2 && seqMatches[1] != "" {
			// 如果找到序号，组合哈希和序号
			return fmt.Sprintf("%s-%s", hash[:3], seqMatches[1])
		}

		return hash[:6]
	}

	// 如果没有文件内容，使用路径组合
	hasher := sha256.New()
	hasher.Write([]byte(zipPath))
	hasher.Write([]byte(innerPath))

	// 获取内部文件的基本名称
	baseName := filepath.Base(innerPath)
	fileName := strings.TrimSuffix(baseName, filepath.Ext(baseName))

	// 提取序号
	seq := ""
	// 如果文件名包含下划线，尝试提取序号部分
	if strings.Contains(fileName, "_") {
		parts := strings.Split(fileName, "_")
		if len(parts) > 0 {
			lastPart := parts[len(parts)-1]
			hasher.Write([]byte(lastPart)) // 使用最后一部分作为序号
			seq = lastPart
		}
	}

	// 如果有父ID，添加到哈希中
	if parentID != "" {
		hasher.Write([]byte(parentID))
	}

	// 获取哈希值的前6个字符
	hash := fmt.Sprintf("%x", hasher.Sum(nil))
	if seq != "" {
		// 如果有序号，返回"哈希前缀-序号"格式
		return fmt.Sprintf("%s-%s", hash[:3], seq)
	}
	return hash[:6]
}
