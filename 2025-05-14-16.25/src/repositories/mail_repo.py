from src.models import db
from src.models.models import Email, EmailAttachment

class MailRepository:
    """邮件存储库类，处理与邮件相关的数据库操作"""
    
    @staticmethod
    def get_email(email_id):
        """根据ID获取邮件"""
        return Email.query.get(email_id)
    
    @staticmethod
    def get_email_by_uid(uid, subject):
        """根据UID和主题获取邮件"""
        return Email.query.filter_by(uid=uid, subject=subject).first()
    
    @staticmethod
    def get_unprocessed_emails():
        """获取所有未处理的邮件"""
        return Email.query.filter_by(processed=False).all()
    
    @staticmethod
    def get_emails_by_sender(sender):
        """根据发件人获取邮件"""
        return Email.query.filter_by(sender=sender).all()
    
    @staticmethod
    def get_emails_by_user(user_id):
        """获取分配给特定用户的邮件"""
        return Email.query.filter_by(assigned_to=user_id).all()
    
    @staticmethod
    def create_email(uid, subject, sender, content=None, sender_name=None, assigned_to=None):
        """创建新邮件记录"""
        email = Email(
            uid=uid,
            subject=subject,
            sender=sender,
            content=content,
            sender_name=sender_name,
            assigned_to=assigned_to,
            processed=False
        )
        db.session.add(email)
        db.session.commit()
        return email
    
    @staticmethod
    def mark_as_processed(email_id, processed=True):
        """标记邮件为已处理或未处理"""
        email = Email.query.get(email_id)
        if email:
            email.processed = processed
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def assign_to_user(email_id, user_id):
        """将邮件分配给用户"""
        email = Email.query.get(email_id)
        if email:
            email.assigned_to = user_id
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def update_email(email_id, **kwargs):
        """更新邮件信息"""
        email = Email.query.get(email_id)
        if email:
            for key, value in kwargs.items():
                if hasattr(email, key):
                    setattr(email, key, value)
            db.session.commit()
        return email
    
    @staticmethod
    def delete_email(email_id):
        """删除邮件记录"""
        email = Email.query.get(email_id)
        if email:
            db.session.delete(email)
            db.session.commit()
            return True
        return False
    
    # 邮件附件相关方法
    @staticmethod
    def get_attachment(attachment_id):
        """根据ID获取附件"""
        return EmailAttachment.query.get(attachment_id)
    
    @staticmethod
    def get_attachments_by_email(email_id):
        """获取邮件的所有附件"""
        return EmailAttachment.query.filter_by(email_id=email_id).all()
    
    @staticmethod
    def create_attachment(filename, saved_as, file_path, email_id, file_size=None, file_type=None, 
                          file_hash=None):
        """创建新附件记录"""
        attachment = EmailAttachment(
            filename=filename,
            saved_as=saved_as,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            file_hash=file_hash,
            email_id=email_id
        )
        db.session.add(attachment)
        db.session.commit()
        return attachment
    
    @staticmethod
    def update_attachment(attachment_id, **kwargs):
        """更新附件信息"""
        attachment = EmailAttachment.query.get(attachment_id)
        if attachment:
            for key, value in kwargs.items():
                if hasattr(attachment, key):
                    setattr(attachment, key, value)
            db.session.commit()
        return attachment
    
    @staticmethod
    def delete_attachment(attachment_id):
        """删除附件记录"""
        attachment = EmailAttachment.query.get(attachment_id)
        if attachment:
            db.session.delete(attachment)
            db.session.commit()
            return True
        return False 