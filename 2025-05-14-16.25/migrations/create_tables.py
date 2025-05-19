# 邮件表
db.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid VARCHAR(100) NOT NULL,
        subject VARCHAR(255) NOT NULL,
        sender VARCHAR(100) NOT NULL,
        sender_name VARCHAR(100),
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        content TEXT,
        processed BOOLEAN DEFAULT 0,
        assigned_to INTEGER,
        FOREIGN KEY (assigned_to) REFERENCES admin_user(id),
        UNIQUE (uid, subject)
    )
''')

# 添加联合索引
db.execute('CREATE INDEX IF NOT EXISTS idx_emails_uid_subject ON emails (uid, subject)') 