import os
import bcrypt
import sqlite3
from app import create_app
from config import config
from models import db, AdminUser

def reset_admin_password():
    """重置管理员密码为默认值：admin123"""
    # 获取数据库路径
    instance_db_path = os.path.join(os.getcwd(), 'instance', 'app.db')
    root_db_path = os.path.join(os.getcwd(), 'app.db')
    
    # 确定使用哪个数据库文件
    if os.path.exists(instance_db_path):
        db_path = instance_db_path
        print(f"使用实例目录数据库: {instance_db_path}")
    elif os.path.exists(root_db_path):
        db_path = root_db_path
        print(f"使用根目录数据库: {root_db_path}")
    else:
        print("错误：找不到数据库文件")
        return False
    
    try:
        # 方法1：使用SQLite直接更新
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查管理员是否存在
        cursor.execute("SELECT id FROM admin_user WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if admin:
            # 生成新的密码哈希
            password = 'admin123'
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
            
            # 更新密码
            cursor.execute("UPDATE admin_user SET password_hash = ? WHERE username = 'admin'", (password_hash,))
            conn.commit()
            print(f"管理员密码已重置为: {password}")
            print(f"新的密码哈希: {password_hash}")
        else:
            print("未找到管理员用户，将创建新用户")
            
            # 生成密码哈希
            password = 'admin123'
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
            
            # 创建管理员
            cursor.execute(
                "INSERT INTO admin_user (username, password_hash, is_admin) VALUES (?, ?, ?)",
                ('admin', password_hash, 1)
            )
            conn.commit()
            print(f"已创建管理员账户 - 用户名: admin, 密码: {password}")
        
        conn.close()
        
        # 方法2：使用SQLAlchemy ORM（作为备份）
        app = create_app(config['development'])
        with app.app_context():
            admin = AdminUser.query.filter_by(username='admin').first()
            if admin:
                admin.set_password('admin123')
                db.session.commit()
                print("使用ORM更新密码成功")
            else:
                admin = AdminUser(username='admin', is_admin=True)
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("使用ORM创建管理员成功")
        
        return True
    
    except Exception as e:
        print(f"重置密码时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if reset_admin_password():
        print("管理员密码重置成功！请使用以下凭据登录：")
        print("用户名: admin")
        print("密码: admin123")
    else:
        print("管理员密码重置失败！") 