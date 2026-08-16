from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config.orm_config import ORMConfig

# 全局变量：存储 SQLAlchemy Engine 对象（内置连接池）
# 类似于旧系统中的 POOL 全局变量
_engine = None

# 全局变量：存储 Session 工厂对象
_session_factory = None


def get_engine():
    """
    获取 SQLAlchemy Engine 对象（单例模式）
    
    Engine 是 SQLAlchemy 的核心对象，内部包含连接池
    相当于旧系统中的 PooledDB 对象
    
    :return: SQLAlchemy Engine 对象
    """
    global _engine
    # 懒加载：第一次调用时才创建 Engine
    if _engine is None:
        _engine = create_engine(
            ORMConfig.get_database_url(),     # 动态构建数据库连接 URL
            pool_size=ORMConfig.POOL_SIZE,    # 连接池大小
            max_overflow=ORMConfig.MAX_OVERFLOW,  # 最大溢出连接数
            pool_timeout=ORMConfig.POOL_TIMEOUT,  # 获取连接超时时间
            pool_recycle=ORMConfig.POOL_RECYCLE,  # 连接回收时间
            echo=ORMConfig.ECHO,              # 是否打印 SQL 语句
        )
    return _engine


def get_session_factory():
    """
    获取 Session 工厂对象（单例模式）
    
    Session 工厂用于创建数据库会话（Session）
    相当于旧系统中从 POOL 获取 connection
    
    :return: scoped_session 对象
    """
    global _session_factory
    # 懒加载：第一次调用时才创建 Session 工厂
    if _session_factory is None:
        engine = get_engine()
        # 创建 Session 工厂，绑定到 Engine
        _session_factory = scoped_session(sessionmaker(bind=engine))
    return _session_factory


@contextmanager
def orm_session():
    """
    ORM 会话上下文管理器（推荐使用）
    
    类似于旧系统中的 db_cursor() 上下文管理器
    自动管理 Session 的生命周期：创建 -> 提交/回滚 -> 关闭
    
    使用示例:
        with orm_session() as session:
            order = session.query(WmsOrders).filter_by(id=1).first()
            print(order.order_no)
    
    :yield: SQLAlchemy Session 对象
    """
    # 获取 Session 工厂
    session_factory = get_session_factory()
    # 创建一个新的 Session
    session = session_factory()
    try:
        # 将 Session 提供给 with 代码块使用
        yield session
        # 正常结束：提交事务
        session.commit()
        # print("session已经提交")
    except Exception:
        # 发生异常：回滚事务
        session.rollback()
        # print(f"回滚，错误：{Exception}")
        # 重新抛出异常，让调用者处理
        raise
    finally:
        # 无论成功或失败，都关闭 Session（归还连接到连接池）
        session.close()
        # 从 scoped_session 的线程本地注册表中移除，避免同线程后续调用复用已关闭的 Session
        session_factory.remove()