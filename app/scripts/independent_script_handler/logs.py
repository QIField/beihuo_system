import datetime
import logging


class InfoOnlyFilter(logging.Filter):
    """
    只允许 INFO 级别日志通过的过滤器
    """
    def filter(self, record):
        return record.levelno == logging.INFO


class WarningAndAboveFilter(logging.Filter):
    """
    只允许 WARNING 及以上级别日志通过的过滤器
    """
    def filter(self, record):
        return record.levelno >= logging.WARNING


def create_logger():
    # 获取名称为demo的日志实例，同一个名称全局只会创建一个logger对象
    logger = logging.getLogger("demo")
    # 设置logger全局日志等级：DEBUG，代表DEBUG及以上级别日志都会被捕获
    logger.setLevel(logging.DEBUG)

    # 判断当前logger是否已经挂载过处理器Handler
    # 防止函数多次调用，重复添加处理器，造成日志重复打印刷屏
    if logger.handlers:
        # 如果已有处理器，直接返回现有logger，不再重复配置
        return logger

    # 创建日志格式化对象，定义每条日志最终输出的文本模板
    log_format = logging.Formatter(
        # 格式化占位符说明
        # %(asctime)s      日志记录时间
        # %(levelname)-8s  日志级别，占8字符宽度，实现对齐
        # %(filename)s     当前执行的文件名
        # %(lineno)d       打印日志所在代码行号
        # %(message)s      用户传入的日志正文
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        # 自定义时间字符串格式
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 生成时间戳，用于日志文件名区分不同运行批次
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

    # 创建成功日志文件处理器，只记录 INFO 级别日志（正常爬取进度等）
    # mode="a"：追加模式，每次启动程序不会清空旧日志，持续续写
    # encoding="utf-8"：指定文件编码，解决Windows中文乱码，Python3.8可用
    success_url = f"logs/conversion-rate/success/{timestamp}.log"
    success_handler = logging.FileHandler(success_url, mode="a", encoding="utf-8")
    # 给文件处理器绑定上面定义好的日志格式
    success_handler.setFormatter(log_format)
    # 设置最低日志级别为 INFO
    success_handler.setLevel(logging.INFO)
    # 添加过滤器，只保留 INFO 级别日志，过滤掉 WARNING 及以上
    success_handler.addFilter(InfoOnlyFilter())

    # 创建失败日志文件处理器，记录 WARNING、ERROR、CRITICAL 级别日志（警告、错误等）
    error_url = f"logs/conversion-rate/error/{timestamp}.log"
    error_handler = logging.FileHandler(error_url, mode="a", encoding="utf-8")
    # 给文件处理器绑定上面定义好的日志格式
    error_handler.setFormatter(log_format)
    # 设置最低日志级别为 WARNING
    error_handler.setLevel(logging.WARNING)
    # 添加过滤器，只保留 WARNING 及以上级别日志
    error_handler.addFilter(WarningAndAboveFilter())

    # 【可选代码，开启后日志同时打印控制台】
    # 创建控制台输出处理器，日志输出到终端窗口
    console_handler = logging.StreamHandler()
    # 控制台处理器使用同一套日志格式
    console_handler.setFormatter(log_format)
    # 将控制台处理器挂载到logger上
    logger.addHandler(console_handler)

    # 将成功日志文件处理器挂载到logger实例
    logger.addHandler(success_handler)
    # 将失败日志文件处理器挂载到logger实例
    logger.addHandler(error_handler)

    # 返回配置完成的logger对象，供外部调用打印日志
    return logger