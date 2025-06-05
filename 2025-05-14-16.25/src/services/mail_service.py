import os
import uuid
import imaplib
import email
import email.header
from email.utils import parseaddr
from datetime import datetime
from flask import current_app

from src.repositories.mail_repo import MailRepository
from src.repositories.admin_repo import AdminRepository
from src.repositories.order_repo import OrderRepository
from src.services.file_service import FileService

class MailService:
    """邮件服务类，处理与邮件相关的业务逻辑"""
    
    @staticmethod
    def get_email(email_id):
        """根据ID获取邮件"""
        return MailRepository.get_email(email_id)
    
    @staticmethod
    def get_unprocessed_emails():
        """获取所有未处理的邮件"""
        return MailRepository.get_unprocessed_emails()
    
    @staticmethod
    def mark_as_processed(email_id, processed=True):
        """标记邮件为已处理或未处理"""
        return MailRepository.mark_as_processed(email_id, processed)
    
    @staticmethod
    def assign_to_user(email_id, user_id):
        """将邮件分配给用户"""
        return MailRepository.assign_to_user(email_id, user_id)
    
    @staticmethod
    def create_order_from_email(email_id, user_id=None):
        """从邮件创建订单
        
        Args:
            email_id: 邮件ID
            user_id: 用户ID，如果为None则使用当前用户
            
        Returns:
            创建的订单对象
        """
        # 获取邮件
        mail = MailRepository.get_email(email_id)
        if not mail:
            return None
        
        # 创建订单
        order = OrderRepository.create_order(user_id, 'pending')
        if not order:
            return None
        
        # 关联邮件与订单
        order.email_id = mail.id
        OrderRepository.update_order(order.id, email_id=mail.id)
        
        # 标记邮件为已处理
        MailRepository.mark_as_processed(email_id, True)
        
        # 处理附件
        attachments = MailRepository.get_attachments_by_email(email_id)
        for attachment in attachments:
            # 检查附件文件是否存在
            if not os.path.exists(attachment.file_path):
                continue
            
            # 获取文件大小和类型
            file_size = os.path.getsize(attachment.file_path)
            file_type = FileService.detect_file_type(attachment.file_path)
            
            # 计算文件哈希值
            file_hash = FileService.calculate_file_hash(attachment.file_path)
            
            # 创建上传文件记录
            # 使用存档路径，这样即使工作目录被清空，还能恢复文件
            FileRepository.create_uploaded_file(
                filename=attachment.saved_as,
                original_filename=attachment.filename,
                file_path=attachment.file_path,
                file_size=file_size,
                file_type=file_type,
                file_hash=file_hash,
                order_id=order.id
            )
        
        return order
    
    @staticmethod
    def check_emails():
        """检查邮箱中的新邮件
        
        Returns:
            新处理的邮件数量
        """
        # 获取邮箱配置
        imap_server = current_app.config.get('IMAP_SERVER')
        imap_port = current_app.config.get('IMAP_PORT', 993)
        imap_user = current_app.config.get('IMAP_USER')
        imap_password = current_app.config.get('IMAP_PASSWORD')
        
        if not all([imap_server, imap_user, imap_password]):
            current_app.logger.error("邮箱配置不完整")
            return 0
        
        try:
            # 连接到邮箱服务器
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(imap_user, imap_password)
            mail.select('INBOX')
            
            # 搜索未读邮件
            status, data = mail.search(None, 'UNSEEN')
            if status != 'OK' or not data[0]:
                mail.close()
                mail.logout()
                return 0
            
            # 获取邮件ID列表
            email_ids = data[0].split()
            processed_count = 0
            
            # 处理每封邮件
            for email_id in email_ids:
                status, data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # 解析邮件内容
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # 获取邮件主题
                subject = MailService._decode_header(msg['Subject'])
                
                # 获取发件人
                from_header = msg['From']
                sender_name, sender_email = parseaddr(from_header)
                sender_name = MailService._decode_header(sender_name)
                
                # 检查邮件是否已存在
                existing_email = MailRepository.get_email_by_uid(email_id.decode(), subject)
                if existing_email:
                    continue
                
                # 创建邮件记录
                mail_record = MailRepository.create_email(
                    uid=email_id.decode(),
                    subject=subject,
                    sender=sender_email,
                    sender_name=sender_name
                )
                
                # 处理邮件正文
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        # 获取文本内容
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            charset = part.get_content_charset() or 'utf-8'
                            try:
                                body = part.get_payload(decode=True).decode(charset)
                            except:
                                try:
                                    body = part.get_payload(decode=True).decode('gbk')
                                except:
                                    body = "邮件内容解码失败"
                            break
                else:
                    charset = msg.get_content_charset() or 'utf-8'
                    try:
                        body = msg.get_payload(decode=True).decode(charset)
                    except:
                        try:
                            body = msg.get_payload(decode=True).decode('gbk')
                        except:
                            body = "邮件内容解码失败"
                
                # 更新邮件内容
                MailRepository.update_email(mail_record.id, content=body)
                
                # 处理附件
                MailService._process_attachments(msg, mail_record.id)
                
                processed_count += 1
            
            mail.close()
            mail.logout()
            
            return processed_count
        
        except Exception as e:
            current_app.logger.error(f"检查邮件时出错: {str(e)}")
            return 0
    
    @staticmethod
    def _decode_header(header):
        """解码邮件头部信息"""
        if not header:
            return ""
        
        decoded_header = email.header.decode_header(header)
        result = ""
        
        for part, encoding in decoded_header:
            if isinstance(part, bytes):
                if encoding:
                    try:
                        result += part.decode(encoding)
                    except:
                        try:
                            result += part.decode('utf-8')
                        except:
                            try:
                                result += part.decode('gbk')
                            except:
                                result += part.decode('latin1', errors='replace')
                else:
                    try:
                        result += part.decode('utf-8')
                    except:
                        try:
                            result += part.decode('gbk')
                        except:
                            result += part.decode('latin1', errors='replace')
            else:
                result += part
        
        return result
    
    @staticmethod
    def _process_attachments(msg, email_id):
        """处理邮件附件
        
        Args:
            msg: 邮件对象
            email_id: 邮件ID
        """
        # 创建附件存储目录
        attachment_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'email_attachments')
        os.makedirs(attachment_dir, exist_ok=True)
        
        # 处理附件
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            
            # 检查是否为附件
            content_disposition = part.get("Content-Disposition")
            if not content_disposition or "attachment" not in content_disposition:
                continue
            
            # 获取附件文件名
            filename = part.get_filename()
            if not filename:
                filename = f"unknown_{uuid.uuid4().hex[:8]}"
            
            # 解码文件名
            filename = MailService._decode_header(filename)
            
            # 创建安全的文件名
            safe_filename = filename
            for char in r'<>:"/\|?*':
                safe_filename = safe_filename.replace(char, '_')
            
            # 确保文件名唯一
            base, ext = os.path.splitext(safe_filename)
            unique_filename = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
            
            # 保存附件
            file_path = os.path.join(attachment_dir, unique_filename)
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            
            # 获取文件大小和类型
            file_size = os.path.getsize(file_path)
            file_type = FileService.detect_file_type(file_path)
            
            # 计算文件哈希值
            file_hash = FileService.calculate_file_hash(file_path)
            
            # 创建附件记录
            MailRepository.create_attachment(
                filename=filename,
                saved_as=unique_filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                file_hash=file_hash,
                email_id=email_id
            ) 