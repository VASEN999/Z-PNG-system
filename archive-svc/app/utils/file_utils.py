import os
import shutil
import mimetypes
import aiofiles
from pathlib import Path
from typing import Optional, Union, BinaryIO, Dict, Any, List, Tuple
import asyncio

from app.config import settings
from app.utils.hash_utils import calculate_file_hash, generate_unique_filename


async def save_upload_file(
    file_content: bytes,
    original_filename: str,
    category: str = "general",
    calculate_hashes: bool = True
) -> Dict[str, Any]:
    """
    保存上传的文件内容到归档目录
    
    Args:
        file_content: 文件内容（字节）
        original_filename: 原始文件名
        category: 文件分类
        calculate_hashes: 是否计算哈希值
        
    Returns:
        文件信息字典
    """
    # 确保类别目录存在
    category_dir = Path(settings.ARCHIVE_DIR) / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
    # 临时保存文件以计算哈希
    temp_file = Path(settings.TEMP_DIR) / original_filename
    try:
        async with aiofiles.open(temp_file, "wb") as f:
            await f.write(file_content)
        
        # 计算文件哈希值
        hash_results = {}
        if calculate_hashes:
            hash_results = await calculate_file_hash(temp_file)
        
        # 使用哈希值生成唯一文件名
        sha256_hash = hash_results.get("sha256", "")
        stored_filename = generate_unique_filename(original_filename, sha256_hash)
        
        # 存储路径
        file_path = category_dir / stored_filename
        
        # 移动文件到最终位置
        shutil.move(temp_file, file_path)
        
        # 获取文件大小和MIME类型
        file_size = file_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        return {
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "mime_type": mime_type,
            "category": category,
            "sha256_hash": hash_results.get("sha256", ""),
            "md5_hash": hash_results.get("md5", "")
        }
    except Exception as e:
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()
        raise e


async def save_upload_file_stream(
    file_obj: BinaryIO,
    original_filename: str,
    category: str = "general",
    calculate_hashes: bool = True,
    chunk_size: int = 65536
) -> Dict[str, Any]:
    """
    保存上传的文件流到归档目录
    
    Args:
        file_obj: 文件对象
        original_filename: 原始文件名
        category: 文件分类
        calculate_hashes: 是否计算哈希值
        chunk_size: 读取块大小
        
    Returns:
        文件信息字典
    """
    # 确保类别目录存在
    category_dir = Path(settings.ARCHIVE_DIR) / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
    # 临时文件路径
    temp_file = Path(settings.TEMP_DIR) / original_filename
    
    # 初始化哈希计算器
    hashers = {}
    if calculate_hashes:
        for algo in settings.HASH_ALGORITHMS:
            if hasattr(__import__("hashlib"), algo):
                hashers[algo] = getattr(__import__("hashlib"), algo)()
    
    try:
        # 保存文件并计算哈希
        file_size = 0
        async with aiofiles.open(temp_file, "wb") as f:
            chunk = file_obj.read(chunk_size)
            while chunk:
                await f.write(chunk)
                file_size += len(chunk)
                
                # 更新哈希值
                for hasher in hashers.values():
                    hasher.update(chunk)
                
                chunk = file_obj.read(chunk_size)
        
        # 获取哈希结果
        hash_results = {algo: hasher.hexdigest() for algo, hasher in hashers.items()}
        
        # 使用哈希值生成唯一文件名
        sha256_hash = hash_results.get("sha256", "")
        stored_filename = generate_unique_filename(original_filename, sha256_hash)
        
        # 存储路径
        file_path = category_dir / stored_filename
        
        # 移动文件到最终位置
        shutil.move(temp_file, file_path)
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        return {
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "mime_type": mime_type,
            "category": category,
            "sha256_hash": hash_results.get("sha256", ""),
            "md5_hash": hash_results.get("md5", "")
        }
    except Exception as e:
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()
        raise e


async def get_file_content(file_path: Union[str, Path]) -> bytes:
    """
    异步读取文件内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件内容（字节）
    """
    async with aiofiles.open(file_path, "rb") as f:
        return await f.read()


async def delete_file(file_path: Union[str, Path]) -> bool:
    """
    删除文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否成功删除
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception:
        return False 