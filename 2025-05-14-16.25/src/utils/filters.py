from datetime import datetime, timezone

def timeago(dt):
    """
    将日期转换为相对时间（如"5分钟前"）
    
    Args:
        dt: datetime对象
        
    Returns:
        相对时间的字符串表示
    """
    if not dt:
        return ""
    
    # 确保datetime对象有时区信息
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    seconds = diff.total_seconds()
    
    # 定义时间间隔
    minute = 60
    hour = minute * 60
    day = hour * 24
    month = day * 30
    year = day * 365
    
    # 计算相对时间
    if seconds < 10:
        return "刚刚"
    elif seconds < minute:
        return f"{int(seconds)}秒前"
    elif seconds < hour:
        return f"{int(seconds // minute)}分钟前"
    elif seconds < day:
        return f"{int(seconds // hour)}小时前"
    elif seconds < month:
        return f"{int(seconds // day)}天前"
    elif seconds < year:
        return f"{int(seconds // month)}个月前"
    else:
        return f"{int(seconds // year)}年前"
        
def register_filters(app):
    """注册所有自定义过滤器"""
    app.jinja_env.filters["timeago"] = timeago 