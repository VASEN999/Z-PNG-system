package config

import (
	"io/ioutil"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Config 应用配置结构
type Config struct {
	Server struct {
		Address string `yaml:"address"`
		Mode    string `yaml:"mode"` // debug, release
	} `yaml:"server"`

	Storage struct {
		UploadDir    string `yaml:"upload_dir"`
		ConvertedDir string `yaml:"converted_dir"`
		ArchiveDir   string `yaml:"archive_dir"`
	} `yaml:"storage"`

	Conversion struct {
		DPI            int  `yaml:"dpi"`
		DeleteOriginal bool `yaml:"delete_original"`
	} `yaml:"conversion"`
}

// Load 从YAML文件加载配置
func Load(path string) (*Config, error) {
	// 确保配置目录存在
	configDir := filepath.Dir(path)
	if _, err := os.Stat(configDir); os.IsNotExist(err) {
		if err := os.MkdirAll(configDir, 0755); err != nil {
			return nil, err
		}
	}

	// 读取配置文件
	data, err := ioutil.ReadFile(path)
	if err != nil {
		// 如果文件不存在，创建默认配置
		if os.IsNotExist(err) {
			cfg := getDefaultConfig()
			
			// 写入默认配置
			data, err = yaml.Marshal(cfg)
			if err != nil {
				return nil, err
			}
			
			if err := ioutil.WriteFile(path, data, 0644); err != nil {
				return nil, err
			}
			
			return cfg, nil
		}
		return nil, err
	}

	// 解析配置
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}

	return &cfg, nil
}

// 获取默认配置
func getDefaultConfig() *Config {
	var cfg Config
	
	// 服务器配置
	cfg.Server.Address = ":8080"
	cfg.Server.Mode = "debug"
	
	// 存储配置
	cfg.Storage.UploadDir = "storage/uploads"
	cfg.Storage.ConvertedDir = "storage/converted"
	cfg.Storage.ArchiveDir = "storage/archive"
	
	// 转换配置
	cfg.Conversion.DPI = 300
	cfg.Conversion.DeleteOriginal = false
	
	return &cfg
} 