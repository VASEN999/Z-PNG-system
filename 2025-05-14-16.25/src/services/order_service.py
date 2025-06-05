from src.repositories.order_repo import OrderRepository
from src.repositories.file_repo import FileRepository

class OrderService:
    """订单服务类，处理与订单相关的业务逻辑"""
    
    @staticmethod
    def get_order(order_id):
        """根据ID获取订单"""
        return OrderRepository.get_by_id(order_id)
    
    @staticmethod
    def get_order_by_number(order_number):
        """根据订单号获取订单"""
        return OrderRepository.get_by_order_number(order_number)
    
    @staticmethod
    def get_all_orders():
        """获取所有订单"""
        return OrderRepository.get_all_orders()
    
    @staticmethod
    def get_active_order(user_id=None):
        """获取活跃订单"""
        return OrderRepository.get_active_order(user_id)
    
    @staticmethod
    def create_order(user_id=None, status='处理中'):
        """创建新订单"""
        return OrderRepository.create_order(user_id, status)
    
    @staticmethod
    def update_order(order_id, **kwargs):
        """更新订单信息"""
        return OrderRepository.update_order(order_id, **kwargs)
    
    @staticmethod
    def update_order_status(order_id, status):
        """更新订单状态"""
        return OrderRepository.update_order_status(order_id, status)
    
    @staticmethod
    def set_active_order(order_id, user_id=None):
        """设置活跃订单"""
        return OrderRepository.set_active(order_id, user_id)
    
    @staticmethod
    def delete_order(order_id):
        """删除订单及其相关文件"""
        # 先删除订单关联的文件记录
        FileRepository.delete_uploaded_files_by_order(order_id)
        
        # 再删除订单本身
        return OrderRepository.delete_order(order_id)
    
    @staticmethod
    def delete_orders(order_ids):
        """批量删除订单及其相关文件
        
        Args:
            order_ids: 订单ID列表
            
        Returns:
            成功返回True，否则False
        """
        try:
            for order_id in order_ids:
                # 删除每个订单及其关联的文件
                OrderService.delete_order(order_id)
            return True
        except Exception as e:
            print(f"批量删除订单出错: {str(e)}")
            return False
    
    @staticmethod
    def merge_orders(order_ids, user_id=None):
        """合并多个订单"""
        return OrderRepository.merge_orders(order_ids, user_id)
    
    @staticmethod
    def get_order_files(order_id):
        """获取订单的所有上传文件"""
        return FileRepository.get_uploaded_files_by_order(order_id)
    
    @staticmethod
    def get_order_conversions(order_id):
        """获取订单的所有转换文件
        
        Args:
            order_id: 订单ID
            
        Returns:
            转换文件列表
        """
        if not order_id:
            return []
        
        # 确保只返回指定订单的转换文件
        return FileRepository.get_converted_files_by_order(order_id)
    
    @staticmethod
    def get_order_summary(order_id):
        """获取订单摘要信息
        
        Returns:
            包含订单信息、文件数量等的字典
        """
        order = OrderRepository.get_by_id(order_id)
        if not order:
            return None
        
        uploaded_files = FileRepository.get_uploaded_files_by_order(order_id)
        converted_files = FileRepository.get_converted_files_by_order(order_id)
        
        return {
            'order': order.to_dict(),
            'uploaded_count': len(uploaded_files),
            'converted_count': len(converted_files),
            'uploaded_files': [f.to_dict() for f in uploaded_files],
            'converted_files': [f.to_dict() for f in converted_files]
        } 