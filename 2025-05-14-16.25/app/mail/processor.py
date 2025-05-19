import os
import hashlib
import logging
import email
import imaplib
from datetime import datetime
from imap_tools import MailBox, AND
from flask import current_app
from models import db, Email, EmailAttachment

logger = logging.getLogger(__name__)

class MailProcessor:
    """邮件处理类，负责连接邮箱、获取邮件及下载附件"""
    
    def __init__(self, host, port, username, password, mailbox='INBOX'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        # 检查是否是163企业邮箱
        self.is_163_enterprise = 'qiye.163.com' in host.lower()
    
    def connect(self):
        """连接到邮箱服务器并测试连接"""
        try:
            if self.is_163_enterprise:
                # 对163企业邮箱使用原生imaplib
                mail = imaplib.IMAP4_SSL(self.host, self.port)
                mail.login(self.username, self.password)
                logger.info("邮箱连接成功")
                
                # 获取文件夹列表
                status, folder_list = mail.list()
                folder_names = []
                if status == 'OK':
                    for folder in folder_list:
                        if folder:
                            # 解码文件夹名
                            decoded_folder = folder.decode('utf-8')
                            if '"' in decoded_folder:
                                folder_name = decoded_folder.split('"')[3]
                                folder_names.append(folder_name)
                
                logger.info(f"可用邮箱文件夹: {', '.join(folder_names)}")
                mail.logout()
                return True
            else:
                # 对其他邮箱使用imap-tools
                with MailBox(self.host, self.port).login(self.username, self.password) as mailbox:
                    logger.info("邮箱连接成功")
                    folders = mailbox.folder.list()
                    folder_names = [f.name for f in folders]
                    logger.info(f"可用邮箱文件夹: {', '.join(folder_names)}")
                    return True
        except Exception as e:
            logger.error(f"邮箱连接失败: {str(e)}")
            return False
    
    def fetch_emails(self, limit=10, only_unread=True):
        """获取邮件并存储到数据库中"""
        logger.info(f"开始从 {self.username}@{self.host} 获取邮件...")
        
        if self.is_163_enterprise:
            return self._fetch_emails_163(limit, only_unread)
        else:
            return self._fetch_emails_standard(limit, only_unread)
    
    def _fetch_emails_163(self, limit=10, only_unread=True):
        """使用原生imaplib获取163企业邮箱的邮件"""
        try:
            # 连接到邮箱
            mail = imaplib.IMAP4_SSL(self.host, self.port)
            mail.login(self.username, self.password)
            
            # 选择邮箱文件夹
            mail.select(self.mailbox)
            logger.info(f"已选择文件夹: {self.mailbox}")
            
            # 准备查询条件
            search_criteria = '(UNSEEN)' if only_unread else 'ALL'
            
            # 搜索邮件
            status, data = mail.search(None, search_criteria)
            if status != 'OK':
                logger.error(f"搜索邮件失败: {status}")
                mail.logout()
                return []
            
            # 获取邮件ID列表
            email_ids = data[0].split()
            if limit > 0:
                # 限制处理的邮件数量
                email_ids = email_ids[-limit:] if email_ids else []
            
            # 处理新邮件
            new_emails = []
            processed_count = 0
            processed_email_ids = []
            
            for email_id in reversed(email_ids):  # 从最新的邮件开始处理
                processed_count += 1
                
                # 获取邮件内容
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    logger.error(f"获取邮件内容失败: {status}")
                    continue
                
                # 解析邮件
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # 提取邮件信息
                subject = self._decode_header(msg['Subject'])
                uid = email_id.decode('utf-8')  # 使用邮件ID作为UID
                sender_email = msg['From']
                sender_name = None
                
                # 处理格式为 "Name <email@example.com>" 的情况
                if '<' in sender_email and '>' in sender_email:
                    # 只提取邮箱部分，忽略可能包含编码的名称部分
                    sender_email = sender_email.split('<')[1].split('>')[0].strip()
                
                # 检查这封邮件是否处理过
                try:
                    # 使用组合查询避免唯一约束错误
                    existing_email = Email.query.filter_by(uid=uid, subject=subject).first()
                    if existing_email:
                        logger.debug(f"邮件已处理过: {subject}，UID: {uid}")
                        # 将邮件标记为已读
                        if only_unread:
                            mail.store(email_id, '+FLAGS', '\\Seen')
                            logger.debug(f"已将邮件标记为已读: {subject}")
                        processed_email_ids.append(email_id)
                        continue  # 跳过已处理的邮件
                    
                    # 检查是否存在相同UID但主题不同的邮件
                    same_uid_emails = Email.query.filter_by(uid=uid).all()
                    if same_uid_emails:
                        # 如果存在相同UID的邮件，检查主题是否相同
                        same_subject = False
                        for same_uid_email in same_uid_emails:
                            if same_uid_email.subject == subject:
                                same_subject = True
                                logger.debug(f"邮件已处理过: {subject}，UID: {uid}")
                                # 将邮件标记为已读
                                if only_unread:
                                    mail.store(email_id, '+FLAGS', '\\Seen')
                                    logger.debug(f"已将邮件标记为已读: {subject}")
                                processed_email_ids.append(email_id)
                                break
                        
                        if same_subject:
                            continue  # 跳过已处理的邮件
                        
                        # 生成一个新的唯一UID
                        uid = f"{uid}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        logger.info(f"发现重复UID，生成新UID: {uid}")
                except Exception as e:
                    logger.error(f"检查邮件存在性时出错: {str(e)}")
                
                try:
                    logger.info(f"处理来自 {sender_email} 的邮件: {subject}，UID: {uid}")
                    
                    # 获取邮件内容
                    content = ""
                    if msg.is_multipart():
                        # 如果邮件包含多个部分
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            
                            # 跳过附件
                            if "attachment" in content_disposition:
                                continue
                            
                            # 提取文本内容
                            if content_type == "text/plain" or content_type == "text/html":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    try:
                                        content += payload.decode(charset)
                                    except UnicodeDecodeError:
                                        content += payload.decode('utf-8', errors='replace')
                    else:
                        # 如果邮件是纯文本
                        payload = msg.get_payload(decode=True)
                        if payload:
                            charset = msg.get_content_charset() or 'utf-8'
                            try:
                                content += payload.decode(charset)
                            except UnicodeDecodeError:
                                content += payload.decode('utf-8', errors='replace')
                    
                    # 创建邮件记录
                    email_record = Email(
                        uid=uid,
                        subject=subject,
                        sender=sender_email,
                        sender_name=sender_name,
                        received_at=datetime.now(),  # 使用当前时间
                        content=content,
                        processed=False
                    )
                    db.session.add(email_record)
                    db.session.flush()  # 获取ID但不提交
                    
                    # 处理附件
                    attachments_dir = os.path.join(current_app.config['UPLOAD_FOLDER'])
                    
                    # 提取附件
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        
                        # 检查是否有文件名，即是否为附件
                        filename = part.get_filename()
                        if filename:
                            attachment = self._save_attachment(email_record, part, filename)
                            if attachment:
                                db.session.add(attachment)
                    new_emails.append(email_record)
                    processed_email_ids.append(email_id)
                    
                    # 将邮件标记为已读
                    if only_unread:
                        mail.store(email_id, '+FLAGS', '\\Seen')
                        logger.debug(f"已将邮件标记为已读: {subject}")
                    
                    logger.info(f"成功处理邮件: {subject}")
                    
                except Exception as e:
                    logger.error(f"处理邮件时出错: {str(e)}")
                    continue
            
            # 提交数据库事务
            if new_emails:
                db.session.commit()
                logger.info(f"成功保存 {len(new_emails)} 封新邮件到数据库")
            
            logger.info(f"本次共处理 {processed_count} 封邮件，新增 {len(new_emails)} 封")
            
            # 关闭连接
            mail.logout()
            
            return new_emails
            
        except Exception as e:
            logger.error(f"获取邮件时出错: {str(e)}")
            db.session.rollback()
            return []
    
    def _decode_header(self, header):
        """解码邮件头"""
        if not header:
            return ""
        
        try:
            decoded_header = email.header.decode_header(header)
            result = ""
            for data, charset in decoded_header:
                if isinstance(data, bytes):
                    if charset:
                        try:
                            result += data.decode(charset)
                        except UnicodeDecodeError:
                            result += data.decode('utf-8', errors='replace')
                    else:
                        try:
                            result += data.decode('utf-8')
                        except UnicodeDecodeError:
                            result += data.decode('utf-8', errors='replace')
                else:
                    result += str(data)
            return result
        except Exception as e:
            logger.error(f"解码邮件头时出错: {str(e)}")
            return header
    
    def _fetch_emails_standard(self, limit=10, only_unread=True):
        """使用imap-tools获取标准邮箱的邮件"""
        try:
            with MailBox(self.host, self.port).login(self.username, self.password) as mailbox:
                # 选择邮箱文件夹
                mailbox.folder.set(self.mailbox)
                logger.info(f"已选择文件夹: {self.mailbox}")
                
                # 准备查询条件
                criteria = None
                if only_unread:
                    criteria = AND(seen=False)
                
                # 处理新邮件
                new_emails = []
                processed_count = 0
                processed_uids = []
                
                # 从最新的邮件开始处理
                for msg in mailbox.fetch(criteria=criteria, reverse=True, limit=limit):
                    processed_count += 1
                    
                    # 提取发件人信息
                    sender_email = msg.from_
                    sender_name = None
                    # 处理格式为 "Name <email@example.com>" 的情况
                    if '<' in sender_email and '>' in sender_email:
                        # 只提取邮箱部分，忽略可能包含编码的名称部分
                        sender_email = sender_email.split('<')[1].split('>')[0].strip()
                    
                    # 检查这封邮件是否处理过
                    try:
                        # 使用组合查询避免唯一约束错误
                        existing_email = Email.query.filter_by(uid=str(msg.uid), subject=msg.subject).first()
                        if existing_email:
                            logger.debug(f"邮件已处理过: {msg.subject}，UID: {msg.uid}")
                            # 将邮件标记为已读
                            if only_unread:
                                mailbox.seen([msg.uid], True)
                                logger.debug(f"已将邮件标记为已读: {msg.subject}")
                            processed_uids.append(msg.uid)
                            continue  # 跳过已处理的邮件
                        
                        # 检查是否存在相同UID但主题不同的邮件
                        same_uid_emails = Email.query.filter_by(uid=str(msg.uid)).all()
                        if same_uid_emails:
                            # 如果存在相同UID的邮件，检查主题是否相同
                            same_subject = False
                            for same_uid_email in same_uid_emails:
                                if same_uid_email.subject == msg.subject:
                                    same_subject = True
                                    logger.debug(f"邮件已处理过: {msg.subject}，UID: {msg.uid}")
                                    # 将邮件标记为已读
                                    if only_unread:
                                        mailbox.seen([msg.uid], True)
                                        logger.debug(f"已将邮件标记为已读: {msg.subject}")
                                    processed_uids.append(msg.uid)
                                    break
                            
                            if same_subject:
                                continue  # 跳过已处理的邮件
                            
                            # 生成一个新的唯一UID
                            new_uid = f"{msg.uid}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            logger.info(f"发现重复UID，生成新UID: {new_uid}")
                            msg_uid = new_uid
                        else:
                            msg_uid = str(msg.uid)
                    except Exception as e:
                        logger.error(f"检查邮件存在性时出错: {str(e)}")
                        msg_uid = f"{msg.uid}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    try:
                        logger.info(f"处理来自 {sender_email} 的邮件: {msg.subject}，UID: {msg_uid}")
                        
                        # 获取邮件内容
                        content = ""
                        if msg.text:
                            content += msg.text
                        if msg.html:
                            content += msg.html
                        
                        # 创建邮件记录
                        email_record = Email(
                            uid=msg_uid,
                            subject=msg.subject,
                            sender=sender_email,
                            sender_name=sender_name,
                            received_at=msg.date,
                            content=content,
                            processed=False
                        )
                        db.session.add(email_record)
                        db.session.flush()  # 获取ID但不提交
                        
                        # 处理附件
                        attachments_dir = os.path.join(current_app.config['UPLOAD_FOLDER'])
                        
                        for att in msg.attachments:
                            if att.filename:
                                attachment = self._save_attachment(email_record, att, att.filename)
                                if attachment:
                                    db.session.add(attachment)
                        
                        new_emails.append(email_record)
                        processed_uids.append(msg.uid)
                        
                        # 将邮件标记为已读
                        if only_unread:
                            mailbox.seen([msg.uid], True)
                            logger.debug(f"已将邮件标记为已读: {msg.subject}")
                        
                        logger.info(f"成功处理邮件: {msg.subject}")
                        
                    except Exception as e:
                        logger.error(f"处理邮件时出错: {str(e)}")
                        continue
                
                # 提交数据库事务
                if new_emails:
                    db.session.commit()
                    logger.info(f"成功保存 {len(new_emails)} 封新邮件到数据库")
                
                logger.info(f"本次共处理 {processed_count} 封邮件，新增 {len(new_emails)} 封")
                return new_emails
                
        except Exception as e:
            logger.error(f"获取邮件时出错: {str(e)}")
            db.session.rollback()
            return []
    
    def calculate_file_hash(self, file_path):
        """计算文件哈希值"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希值时出错: {str(e)}")
            return None
    
    def get_file_type(self, filename):
        """获取文件类型"""
        if '.' in filename:
            return filename.rsplit('.', 1)[1].lower()
        return "unknown" 
    
    def _save_attachment(self, email_record, part, filename):
        """保存附件到临时目录而不是工作目录"""
        try:
            # 解码文件名
            filename = self._decode_header(filename)
            
            # 创建临时邮件附件目录 (与工作目录分开)
            temp_attachment_dir = os.path.join(current_app.config['TEMP_FOLDER'], 'mail_attachments', str(email_record.id))
            os.makedirs(temp_attachment_dir, exist_ok=True)
            
            # 使用时间戳+原文件名确保文件名唯一
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            safe_filename = f"{timestamp}_{filename}"
            
            # 保存附件到临时目录
            file_path = os.path.join(temp_attachment_dir, safe_filename)
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            
            # 计算哈希值
            file_hash = self.calculate_file_hash(file_path)
            
            # 创建附件记录
            attachment = EmailAttachment(
                filename=filename,
                saved_as=safe_filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                file_type=self.get_file_type(filename),
                file_hash=file_hash,
                email_id=email_record.id
            )
            db.session.add(attachment)
            return attachment
        except Exception as e:
            logger.error(f"保存附件时出错: {str(e)}")
            return None 