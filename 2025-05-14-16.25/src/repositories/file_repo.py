from src.models import db
from src.models.models import UploadedFile, ConvertedFile

class FileRepository:
    """文件存储库类，处理与文件相关的数据库操作"""
    
    @staticmethod
    def get_uploaded_file(file_id):
        """根据ID获取上传的文件"""
        return UploadedFile.query.get(file_id)
    
    @staticmethod
    def get_uploaded_file_by_filename(filename):
        """根据文件名获取上传的文件"""
        return UploadedFile.query.filter_by(filename=filename).first()
    
    @staticmethod
    def get_uploaded_files_by_order(order_id):
        """获取指定订单的所有上传文件"""
        return UploadedFile.query.filter_by(order_id=order_id).all()
    
    @staticmethod
    def get_converted_file(file_id):
        """根据ID获取转换的文件"""
        return ConvertedFile.query.get(file_id)
    
    @staticmethod
    def get_converted_file_by_filename(filename):
        """根据文件名获取转换的文件"""
        return ConvertedFile.query.filter_by(filename=filename).first()
    
    @staticmethod
    def get_converted_files_by_order(order_id):
        """获取指定订单的所有转换文件"""
        return ConvertedFile.query.filter_by(order_id=order_id).all()
    
    @staticmethod
    def get_converted_files_by_source(source_file_id):
        """获取指定源文件的所有转换文件"""
        return ConvertedFile.query.filter_by(source_file_id=source_file_id).all()
    
    @staticmethod
    def get_converted_files_by_hash(source_hash):
        """根据源文件哈希值获取转换文件"""
        return ConvertedFile.query.filter_by(source_hash=source_hash).all()
    
    @staticmethod
    def create_uploaded_file(filename, original_filename, file_path, order_id, file_size=None, 
                            file_type=None, file_hash=None):
        """创建上传文件记录"""
        uploaded_file = UploadedFile(
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            file_hash=file_hash,
            order_id=order_id
        )
        db.session.add(uploaded_file)
        db.session.commit()
        return uploaded_file
    
    @staticmethod
    def create_converted_file(filename, file_path, order_id, source_file_id=None, source_hash=None, 
                             from_zip=False, zip_path=None):
        """创建转换文件记录"""
        converted_file = ConvertedFile(
            filename=filename,
            file_path=file_path,
            source_file_id=source_file_id,
            source_hash=source_hash,
            from_zip=from_zip,
            zip_path=zip_path,
            order_id=order_id
        )
        db.session.add(converted_file)
        db.session.commit()
        return converted_file
    
    @staticmethod
    def delete_uploaded_file(file_id):
        """删除上传文件记录"""
        file = UploadedFile.query.get(file_id)
        if file:
            db.session.delete(file)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def delete_converted_file(file_id):
        """删除转换文件记录"""
        file = ConvertedFile.query.get(file_id)
        if file:
            db.session.delete(file)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def delete_converted_files_by_order(order_id):
        """删除指定订单的所有转换文件记录"""
        ConvertedFile.query.filter_by(order_id=order_id).delete()
        db.session.commit()
        
    @staticmethod
    def delete_uploaded_files_by_order(order_id):
        """删除指定订单的所有上传文件记录"""
        # 先删除关联的转换文件
        FileRepository.delete_converted_files_by_order(order_id)
        
        # 再删除上传文件
        UploadedFile.query.filter_by(order_id=order_id).delete()
        db.session.commit()
    
    @staticmethod
    def update_uploaded_file(file_id, **kwargs):
        """更新上传文件信息"""
        file = UploadedFile.query.get(file_id)
        if file:
            for key, value in kwargs.items():
                if hasattr(file, key):
                    setattr(file, key, value)
            db.session.commit()
        return file
    
    @staticmethod
    def update_converted_file(file_id, **kwargs):
        """更新转换文件信息"""
        file = ConvertedFile.query.get(file_id)
        if file:
            for key, value in kwargs.items():
                if hasattr(file, key):
                    setattr(file, key, value)
            db.session.commit()
        return file 