from src.models import db
from src.models.models import Order
from flask import session

class OrderRepository:
    """订单存储库类，处理与订单相关的数据库操作"""
    
    @staticmethod
    def get_by_id(order_id):
        """根据ID获取订单"""
        return Order.query.get(order_id)
    
    @staticmethod
    def get_by_order_number(order_number):
        """根据订单号获取订单"""
        return Order.query.filter_by(order_number=order_number).first()
    
    @staticmethod
    def get_all_orders():
        """获取所有订单"""
        return Order.query.all()
    
    @staticmethod
    def get_active_order(user_id=None):
        """获取活跃订单
        
        Args:
            user_id: 用户ID，如果为None则获取当前用户的活跃订单
            
        Returns:
            活跃订单对象或None
        """
        if user_id is None:
            user_id = session.get('admin_id')
        
        if user_id:
            return Order.query.filter_by(is_active=True, user_id=user_id).first()
        
        return None
    
    @staticmethod
    def create_order(user_id=None, status='处理中'):
        """创建新订单
        
        Args:
            user_id: 用户ID，如果为None则使用当前用户
            status: 订单状态
            
        Returns:
            新创建的订单对象
        """
        if user_id is None:
            user_id = session.get('admin_id')
        
        order = Order(
            order_number=Order.generate_order_number(),
            user_id=user_id,
            status=status
        )
        db.session.add(order)
        db.session.commit()
        return order
    
    @staticmethod
    def update_order(order_id, **kwargs):
        """更新订单信息
        
        Args:
            order_id: 订单ID
            **kwargs: 需要更新的字段和值
            
        Returns:
            更新后的订单对象
        """
        order = Order.query.get(order_id)
        if order:
            for key, value in kwargs.items():
                if hasattr(order, key):
                    setattr(order, key, value)
            db.session.commit()
        
        return order
    
    @staticmethod
    def update_order_status(order_id, status):
        """更新订单状态
        
        Args:
            order_id: 订单ID
            status: 新状态
            
        Returns:
            更新后的订单对象
        """
        return OrderRepository.update_order(order_id, status=status)
    
    @staticmethod
    def set_active(order_id, user_id=None):
        """设置订单为活跃状态
        
        Args:
            order_id: 要设置为活跃的订单ID
            user_id: 用户ID，如果为None则使用当前用户
            
        Returns:
            操作成功返回True，否则返回False
        """
        if user_id is None:
            user_id = session.get('admin_id')
        
        if user_id:
            # 先将该用户的所有订单设为非活跃
            orders = Order.query.filter_by(user_id=user_id, is_active=True).all()
            for order in orders:
                order.is_active = False
            
            # 将指定订单设为活跃
            order = Order.query.get(order_id)
            if order:
                order.is_active = True
                order.user_id = user_id  # 同时分配给用户
                db.session.commit()
                return True
        
        return False
    
    @staticmethod
    def delete_order(order_id):
        """删除订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        order = Order.query.get(order_id)
        if order:
            db.session.delete(order)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def merge_orders(order_ids, user_id=None):
        """合并多个订单
        
        Args:
            order_ids: 要合并的订单ID列表
            user_id: 用户ID，如果为None则使用当前用户
            
        Returns:
            合并后的新订单对象
        """
        if user_id is None:
            user_id = session.get('admin_id')
        
        orders = [Order.query.get(oid) for oid in order_ids if Order.query.get(oid)]
        if not orders:
            return None
        
        # 创建新的合并订单
        merged_order = Order(
            order_number=Order.generate_order_number(),
            user_id=user_id,
            status='处理中',
            is_merged=True,
            merged_from=','.join([o.order_number for o in orders])
        )
        db.session.add(merged_order)
        db.session.commit()
        
        return merged_order 