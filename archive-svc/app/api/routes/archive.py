import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles
from pathlib import Path

from app.api.schemas import (
    ArchiveFileCreate,
    ArchiveFileUpdate,
    ArchiveFileResponse,
    ArchiveFileVersionResponse,
    FileSearchRequest,
    FileListResponse,
    FileUploadResponse,
    FileDetailResponse,
    ErrorResponse,
)
from app.models import get_db
from app.core.archive_repo import (
    archive_file_repo,
    archive_file_version_repo,
)
from app.utils.hash_utils import calculate_file_hash, find_files_by_hash
from app.utils.file_utils import save_upload_file, get_file_content
from app.config import settings

router = APIRouter()


@router.post(
    "/files",
    response_model=FileUploadResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("general"),
    description: Optional[str] = Form(None),
    tags: Optional[List[str]] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    上传并归档文件
    """
    try:
        # 确保临时目录存在
        temp_dir = Path(settings.TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 临时文件路径
        temp_path = temp_dir / file.filename
        
        # 保存上传的文件到临时目录
        try:
            content = await file.read()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)
            
            # 计算文件哈希
            hashes = await calculate_file_hash(temp_path)
            
            # 检查文件是否已存在（基于哈希）
            if hashes.get("sha256"):
                existing_file = await archive_file_repo.get_by_hash(db, hashes["sha256"])
                if existing_file:
                    # 文件已存在，返回现有文件信息
                    return FileUploadResponse(
                        success=True,
                        message="文件已存在于归档中",
                        file=ArchiveFileResponse.from_orm(existing_file),
                    )
            
            # 将文件移动到归档目录并保存文件信息
            file_size = os.path.getsize(temp_path)
            
            # 确保分类目录存在
            category_dir = Path(settings.ARCHIVE_DIR) / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            hash_prefix = hashes.get("sha256", "")[:8] if hashes.get("sha256") else ""
            timestamp = int(Path(temp_path).stat().st_mtime)
            stored_filename = f"{timestamp}_{hash_prefix}_{file.filename}"
            
            # 目标路径
            dest_path = category_dir / stored_filename
            
            # 移动文件
            shutil.move(temp_path, dest_path)
            
            # 创建文件记录
            file_data = {
                "original_filename": file.filename,
                "stored_filename": stored_filename,
                "file_path": str(dest_path),
                "file_size": file_size,
                "mime_type": file.content_type,
                "sha256_hash": hashes.get("sha256", ""),
                "md5_hash": hashes.get("md5", ""),
                "category": category,
                "description": description,
                "tags": tags,
            }
            
            db_file = await archive_file_repo.create(db, obj_in=file_data)
            
            return FileUploadResponse(
                success=True,
                message="文件上传成功",
                file=ArchiveFileResponse.from_orm(db_file),
            )
        finally:
            # 确保清理临时文件
            if temp_path.exists():
                temp_path.unlink()
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}",
        )


@router.get(
    "/files",
    response_model=FileListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_files(
    query: Optional[str] = None,
    category: Optional[str] = None,
    hash_value: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    获取归档文件列表，支持搜索和过滤
    """
    try:
        files = await archive_file_repo.search_files(
            db,
            query=query,
            category=category,
            hash_value=hash_value,
            tags=tags,
            skip=skip,
            limit=limit,
        )
        
        # 计算总数（不考虑分页）
        total_count = len(files)  # 简化实现，实际应该使用COUNT查询
        
        return FileListResponse(
            success=True,
            message="获取文件列表成功",
            total=total_count,
            skip=skip,
            limit=limit,
            data=[ArchiveFileResponse.from_orm(file) for file in files],
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件列表失败: {str(e)}",
        )


@router.get(
    "/files/{file_id}",
    response_model=FileDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_file(
    file_id: int,
    include_versions: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    获取归档文件详情
    """
    try:
        file = await archive_file_repo.get(db, file_id)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到ID为{file_id}的文件",
            )
        
        response = FileDetailResponse(
            success=True,
            message="获取文件详情成功",
            file=ArchiveFileResponse.from_orm(file),
        )
        
        # 如果需要包含版本信息
        if include_versions:
            versions = await archive_file_version_repo.get_versions_by_parent(db, file_id)
            response.versions = [ArchiveFileVersionResponse.from_orm(v) for v in versions]
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件详情失败: {str(e)}",
        )


@router.get(
    "/files/hash/{hash_value}",
    response_model=FileDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_file_by_hash(
    hash_value: str,
    db: AsyncSession = Depends(get_db),
):
    """
    根据哈希值获取归档文件
    """
    try:
        file = await archive_file_repo.get_by_hash(db, hash_value)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到哈希值为{hash_value}的文件",
            )
        
        return FileDetailResponse(
            success=True,
            message="获取文件详情成功",
            file=ArchiveFileResponse.from_orm(file),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件失败: {str(e)}",
        )


@router.put(
    "/files/{file_id}",
    response_model=FileDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def update_file(
    file_id: int,
    file_update: ArchiveFileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新归档文件信息
    """
    try:
        # 获取文件
        file = await archive_file_repo.get(db, file_id)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到ID为{file_id}的文件",
            )
        
        # 更新文件
        updated_file = await archive_file_repo.update(
            db, db_obj=file, obj_in=file_update.dict(exclude_unset=True)
        )
        
        return FileDetailResponse(
            success=True,
            message="文件信息更新成功",
            file=ArchiveFileResponse.from_orm(updated_file),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新文件信息失败: {str(e)}",
        )


@router.delete(
    "/files/{file_id}",
    response_model=FileDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def delete_file(
    file_id: int,
    permanent: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    删除归档文件（软删除或永久删除）
    """
    try:
        # 获取文件
        file = await archive_file_repo.get(db, file_id)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到ID为{file_id}的文件",
            )
        
        if permanent:
            # 永久删除
            await archive_file_repo.delete(db, id=file_id)
            
            # 删除物理文件
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
            
            return FileDetailResponse(
                success=True,
                message="文件已永久删除",
                file=ArchiveFileResponse.from_orm(file),
            )
        else:
            # 软删除
            updated_file = await archive_file_repo.soft_delete(db, id=file_id)
            
            return FileDetailResponse(
                success=True,
                message="文件已标记为删除",
                file=ArchiveFileResponse.from_orm(updated_file),
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文件失败: {str(e)}",
        )


@router.get(
    "/files/{file_id}/download",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    下载归档文件
    """
    try:
        # 获取文件
        file = await archive_file_repo.get(db, file_id)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到ID为{file_id}的文件",
            )
        
        # 检查文件是否存在
        if not os.path.exists(file.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在于存储系统中",
            )
        
        # 读取文件内容
        content = await get_file_content(file.file_path)
        
        # 返回文件
        headers = {
            "Content-Disposition": f"attachment; filename={file.original_filename}"
        }
        
        return Response(
            content=content,
            media_type=file.mime_type or "application/octet-stream",
            headers=headers,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}",
        ) 