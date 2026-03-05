"""
数据同步后处理服务
处理定时更新完成后的各种后续操作
"""

from app.services.cart_service.cart_auto_cleanup import CartAutoCleanupService


class UpdateCompletionHandler:
    """更新完成后处理服务类"""
    
    def __init__(self):
        self.cart_cleanup_service = CartAutoCleanupService()
    
    def handle_post_update_operations(self):
        """
        处理更新完成后的所有后续操作
        目前主要是购物车自动清理，未来可扩展其他功能
        """
        results = {
            'timestamp': None,
            'cart_cleanup': None,
            'status': 'success'
        }
        
        from datetime import datetime
        results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. 执行购物车自动清理（库存大于20的商品）
        try:
            print("🕒 开始执行定时更新后的购物车自动清理...")
            cleanup_results = self.cart_cleanup_service.cleanup_after_data_update()
            
            # 统计清理结果
            total_deleted = sum(
                r.get('deleted_count', 0) 
                for r in cleanup_results 
                if r.get('status') == 'success'
            )
            
            results['cart_cleanup'] = {
                'status': 'completed',
                'results': cleanup_results,
                'total_deleted': total_deleted,
                'message': f'共清理 {total_deleted} 个高库存商品'
            }
            
            if total_deleted > 0:
                print(f"✅ 定时更新后清理完成：共删除 {total_deleted} 个高库存商品")
            else:
                print("ℹ️ 定时更新后清理完成：无高库存商品需要清理")
                
        except Exception as e:
            results['cart_cleanup'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['status'] = 'partial_success'
            print(f"❌ 定时更新后清理失败: {str(e)}")
        
        # 2. 可以在这里添加其他更新后的处理逻辑
        # 例如：发送通知、更新统计信息等
        
        return results
    
    def execute_cleanup_only(self):
        """
        仅执行购物车清理（简化版本）
        用于只需要清理功能的场景
        """
        try:
            return self.cart_cleanup_service.cleanup_after_data_update()
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }