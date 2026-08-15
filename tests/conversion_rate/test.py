# 导入python标准日志库
import logging
# 导入操作系统模块，用于路径相关操作
import os

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

    # 创建文件输出处理器，负责把日志写入本地文件
    # "app.log"：相对路径，日志生成在终端执行命令的工作目录
    # mode="a"：追加模式，每次启动程序不会清空旧日志，持续续写
    # encoding="utf-8"：指定文件编码，解决Windows中文乱码，Python3.8可用
    file_handler = logging.FileHandler("logs/app.log", mode="a", encoding="utf-8")
    # 给文件处理器绑定上面定义好的日志格式
    file_handler.setFormatter(log_format)

    # 【可选代码，开启后日志同时打印控制台】
    # 创建控制台输出处理器，日志输出到终端窗口
    console_handler = logging.StreamHandler()
    # 控制台处理器使用同一套日志格式
    console_handler.setFormatter(log_format)
    # 将控制台处理器挂载到logger上
    logger.addHandler(console_handler)

    # 将文件输出处理器挂载到logger实例，日志才会写入文件
    logger.addHandler(file_handler)

    # 返回配置完成的logger对象，供外部调用打印日志
    return logger

# 执行函数，生成配置完成的全局日志对象
logger = create_logger()

# 输出INFO级别日志，测试中文是否正常写入日志文件
logger.info("="*100)
logger.info("测试中文日志内容")
logger.info("="*100)
logger.error("测试中文错误日志内容")
logger.info("="*100)
logger.info("测试中文日志内容")


