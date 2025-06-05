import os
import hashlib
from typing import Dict, List, Optional, Tuple, Union
import aiofiles
import asyncio
from pathlib import Path

from app.config import settings


async def calculate_file_hash(
    file_path: Union[str, Path], 
    algorithms: List[str] = None,
    chunk_size: int = 65536
) -> Dict[str, str]:
    """
    异步计算文件哈希值
    
    Args:
        file_path: 文件路径
        algorithms: 使用的哈希算法列表，默认使用settings中的配置
        chunk_size: 读取文件的块大小
        
    Returns:
        包含不同算法哈希值的字典，如 {"sha256": "...", "md5": "..."}
    """
    if algorithms is None:
        algorithms = settings.HASH_ALGORITHMS
    
    # 初始化哈希对象
    hashers = {algo: hashlib.new(algo) for algo in algorithms if hasattr(hashlib, algo)}
    
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                for hasher in hashers.values():
                    hasher.update(chunk)
        
        # 获取所有哈希值
        return {algo: hasher.hexdigest() for algo, hasher in hashers.items()}
    except Exception as e:
        # 如果出现错误，返回空字典
        print(f"计算文件哈希时出错: {str(e)}")
        return {}


async def verify_file_hash(file_path: Union[str, Path], expected_hash: str, algorithm: str = None) -> bool:
    """
    验证文件哈希是否匹配
    
    Args:
        file_path: 文件路径
        expected_hash: 期望的哈希值
        algorithm: 哈希算法，默认使用settings中的默认算法
        
    Returns:
        哈希值是否匹配
    """
    if algorithm is None:
        algorithm = settings.DEFAULT_HASH_ALGORITHM
    
    hash_results = await calculate_file_hash(file_path, [algorithm])
    calculated_hash = hash_results.get(algorithm, "")
    
    return calculated_hash == expected_hash


async def find_files_by_hash(
    hash_value: str, 
    search_dir: Union[str, Path] = None, 
    algorithm: str = None,
    recursive: bool = True
) -> List[Path]:
    """
    根据哈希值查找文件
    
    Args:
        hash_value: 要查找的哈希值
        search_dir: 搜索目录，默认使用settings中的ARCHIVE_DIR
        algorithm: 哈希算法，默认使用settings中的DEFAULT_HASH_ALGORITHM
        recursive: 是否递归搜索子目录
        
    Returns:
        匹配哈希值的文件路径列表
    """
    if algorithm is None:
        algorithm = settings.DEFAULT_HASH_ALGORITHM
    
    if search_dir is None:
        search_dir = settings.ARCHIVE_DIR
    
    search_path = Path(search_dir)
    matching_files = []
    
    # 获取搜索路径中的所有文件
    if recursive:
        files = [f for f in search_path.glob("**/*") if f.is_file()]
    else:
        files = [f for f in search_path.glob("*") if f.is_file()]
    
    # 并行计算所有文件的哈希值
    tasks = [calculate_file_hash(f, [algorithm]) for f in files]
    hash_results = await asyncio.gather(*tasks)
    
    # 找出匹配的文件
    for i, hash_result in enumerate(hash_results):
        if hash_result.get(algorithm, "") == hash_value:
            matching_files.append(files[i])
    
    return matching_files


def generate_unique_filename(original_filename: str, hash_value: str = None) -> str:
    """
    生成唯一的文件名
    
    Args:
        original_filename: 原始文件名
        hash_value: 文件哈希值，如果提供则使用其一部分
        
    Returns:
        唯一文件名
    """
    timestamp = int(asyncio.get_event_loop().time() * 1000)
    random_part = os.urandom(4).hex()
    
    # 获取文件扩展名
    _, ext = os.path.splitext(original_filename)
    
    # 使用哈希值一部分（如果有）
    hash_part = ""
    if hash_value and len(hash_value) >= 8:
        hash_part = hash_value[:8]
    
    # 组合唯一文件名
    unique_name = f"{timestamp}_{random_part}"
    if hash_part:
        unique_name = f"{unique_name}_{hash_part}"
    
    return f"{unique_name}{ext}" 