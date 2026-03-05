import pandas as pd
import datetime
import numpy as np
from datetime import datetime, timedelta
import pymysql
import os
from pathlib import Path
from .database_connection import get_db_connection  # 使用统一的连接池实现


def get_new_order_number():
    """从数据库获取最新的订单号并生成新订单号"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # 使用事务和锁确保订单号生成的唯一性
    try:
        # 开启事务
        connection.begin()
        
        # 查询最新的订单号，使用FOR UPDATE加锁
        query = "SELECT order_number FROM crmapp_order_number WHERE company = '厦门华禹' ORDER BY datetime DESC, id DESC LIMIT 1 FOR UPDATE"
        cursor.execute(query)
        result = cursor.fetchone()
        
        current_date = datetime.now()
        # 计算当前时间减三天作为订单日期
        three_days_ago = current_date - timedelta(days=3)
        new_date_part = three_days_ago.strftime('%y%m%d')  # 如 '260128'（三天前的日期）
        
        if result:
            last_order_number = result['order_number']
            # 解析订单号格式 'SXXXXXXX-XXXXX'，例如 'S02501203-01598'
            # 日期部分是 S + 8位数字，序号部分是 - + 数字
            import re
            match = re.match(r'^S(\d{8})-(\d+)$', last_order_number)
            if match:
                # 提取序号部分并递增
                number_part = int(match.group(2))  # 序号，如 1598
                new_number_part = number_part + 1
                # 格式化序号为至少5位，不足前面补0
                formatted_number = f"{new_number_part:05d}"
            else:
                # 如果不符合预期格式，使用默认值
                formatted_number = "00001"
        else:
            # 如果没有历史订单，使用默认值
            formatted_number = "00001"
        
        # 生成新订单号，如 'S0260128-00001'（使用三天前的日期）
        new_order_number = f"S0{new_date_part}-{formatted_number}"
        
        # 插入新订单号到数据库
        insert_query = "INSERT INTO crmapp_order_number (company, datetime, order_number) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, ('厦门华禹', current_date, new_order_number))
        
        # 提交事务
        connection.commit()
        
        return new_order_number
    except Exception as e:
        # 回滚事务
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()


def preallocate_order_numbers(count):
    """预分配多个订单号"""
    if count <= 0:
        return []
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # 开启事务
        connection.begin()
        
        # 查询最新的订单号，使用FOR UPDATE加锁
        query = "SELECT order_number FROM crmapp_order_number WHERE company = '厦门华禹' ORDER BY datetime DESC, id DESC LIMIT 1 FOR UPDATE"
        cursor.execute(query)
        result = cursor.fetchone()
        
        current_date = datetime.now()
        # 计算当前时间减三天作为订单日期
        three_days_ago = current_date - timedelta(days=3)
        new_date_part = three_days_ago.strftime('%y%m%d')  # 如 '260128'（三天前的日期）
        
        if result:
            last_order_number = result['order_number']
            # 解析订单号格式 'SXXXXXXX-XXXXX'，例如 'S02501203-01598'
            import re
            match = re.match(r'^S(\d{8})-(\d+)$', last_order_number)
            if match:
                # 提取序号部分作为起始值
                start_number = int(match.group(2))  # 序号，如 1598
            else:
                # 如果不符合预期格式，使用默认值
                start_number = 0
        else:
            # 如果没有历史订单，从1开始
            start_number = 0
        
        # 生成连续的订单号
        order_numbers = []
        for i in range(count):
            next_number = start_number + i + 1
            formatted_number = f"{next_number:05d}"  # 格式化序号为至少5位
            # 使用三天前的日期生成订单号
            new_order_number = f"S0{new_date_part}-{formatted_number}"
            order_numbers.append(new_order_number)
            
            # 同时插入数据库
            insert_query = "INSERT INTO crmapp_order_number (company, datetime, order_number) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, ('厦门华禹', current_date, new_order_number))
        
        # 提交事务
        connection.commit()
        
        return order_numbers
    except Exception as e:
        # 回滚事务
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()


def init_database():
    """初始化数据库表，如果不存在则创建并插入初始数据"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # 检查表是否已经存在
    check_table_sql = """
    SELECT COUNT(*) AS count 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'crmapp_order_number'
    """
    cursor.execute(check_table_sql)
    result = cursor.fetchone()
    
    table_exists = result['count'] > 0 if result else False
    
    if not table_exists:
        # 创建表
        create_table_sql = """
        CREATE TABLE crmapp_order_number (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company VARCHAR(255),
            datetime DATETIME,
            order_number VARCHAR(255)
        ) DEFAULT CHARSET=utf8mb4
        """
        cursor.execute(create_table_sql)
        print("创建了数据库表 crmapp_order_number")
        
        # 插入两条初始数据
        insert_data_sql = """
        INSERT INTO crmapp_order_number (company, datetime, order_number) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_data_sql, ('厦门华禹', '2026-01-01 00:00:00', 'S02501203-01598'))
        cursor.execute(insert_data_sql, ('广州龙星景丰', '2026-01-01 00:00:00', 'BJ251203369'))
        print("插入了两条初始数据")
    else:
        print("数据库表 crmapp_order_number 已存在")
    
    connection.commit()
    cursor.close()
    connection.close()


def start(single_file_path=None, output_dir=None, allocated_order_number=None):
    # 如果没有预分配订单号，则初始化数据库
    if not allocated_order_number:
        init_database()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 确定资源文件目录 - 根据当前项目结构调整路径
    # 从 app/utils/ 目录向上两级到达项目根目录，然后进入 static 目录
    project_root = os.path.dirname(os.path.dirname(current_dir))
    resource_dir = os.path.join(project_root, 'static', '厦门华禹贸易有限公司报价清单')
    
    # 如果指定了特定的文件路径，使用该路径；否则使用默认路径
    if single_file_path:
        excel_file_path = single_file_path
    else:
        # 更新Excel文件名为实际存在的文件名
        excel_file_path = os.path.join(resource_dir, "厦门华禹单据模板.xlsx")
    
    # 如果指定了输出目录，使用该目录；否则使用当前目录
    if output_dir:
        output_directory = output_dir
    else:
        output_directory = current_dir
    
    djt_df = pd.read_excel(excel_file_path, sheet_name="单据头", converters={"客服电话": str, "电话": str})
    mx_df = pd.read_excel(excel_file_path, sheet_name="明细", converters={"零件编码": str, "原厂编码": str, "单据编号": str})
    djt_df = djt_df.replace(np.nan, "")
    mx_df = mx_df.replace(np.nan, "")
    
    # 如果有预分配的订单号，直接使用；否则生成新的订单号
    if allocated_order_number:
        new_order_number = allocated_order_number
    else:
        new_order_number = get_new_order_number()
    
    # 计算当前时间减三天作为单据日期
    three_days_ago = datetime.now() - timedelta(days=3)
    formatted_date = three_days_ago.strftime('%Y.%m.%d')  # 格式化为 YYYY.MM.DD

    # 读取框架文件
    framework_file = os.path.join(resource_dir, 'framework.txt')
    with open(framework_file, 'r', encoding='utf-8') as f:
        framework = f.read()
    framework = str(framework).replace("Z1D", list(djt_df['logo'])[0])
    framework = str(framework).replace("Z2D", list(djt_df['logo下描述'])[0])
    framework = str(framework).replace("Z3D", list(djt_df['单据头'])[0])
    framework = str(framework).replace("Z4D", list(djt_df['发货人'])[0])
    framework = str(framework).replace("Z5D", list(djt_df['销售人'])[0])
    framework = str(framework).replace("Z6D", list(djt_df['验货人'])[0])
    framework = str(framework).replace("Z7D", list(djt_df['客服地址'])[0])
    framework = str(framework).replace("Z8D", list(djt_df['客服电话'])[0])
    framework = str(framework).replace("Z9D", formatted_date)  # 使用计算的时间代替从Excel读取的数据
    framework = str(framework).replace("Z10D", list(djt_df['客户名称'])[0])
    framework = str(framework).replace("Z11D", new_order_number)  # 使用数据库生成的新订单号
    framework = str(framework).replace("Z12D", list(djt_df['地址'])[0])
    framework = str(framework).replace("Z13D", list(djt_df['联系人'])[0])
    framework = str(framework).replace("Z14D", list(djt_df['电话'])[0])
    framework = str(framework).replace("Z15D", list(djt_df['送货方式'])[0])
    framework = str(framework).replace("Z16D", list(djt_df['运费承担'])[0])
    framework = str(framework).replace("Z17D", list(djt_df['结算方式'])[0])
    framework = str(framework).replace("Z18D", list(djt_df['备注'])[0])

    # 序号	单据日期	单据编号	零件编码	原厂编码	零件名	出库数	售价	金额
    val1_list = list(mx_df['序号'])
    mx_df['出库数'] = mx_df['出库数'].astype(float)
    mx_df['售价'] = mx_df['售价'].astype(float)
    mx_df['金额'] = mx_df['金额'].astype(float)

    val4_list = list(mx_df['零件编码'])
    val5_list = list(mx_df['原厂编码'])
    val6_list = list(mx_df['零件名'])
    val7_list = list(mx_df['出库数'])
    val8_list = list(mx_df['售价'])
    val9_list = list(mx_df['金额'])

    table_list = ""
    for k, v in enumerate(val1_list):
        text = """
                <tr>
                    <td>E1E</td>
                    <td>E2E</td>
                    <td>E3E</td>
                    <td>E4E</td>
                    <td>E5E</td>
                    <td>E6E</td>
                    <td>E7E</td>
                </tr>
            """
        text = text.replace("E1E", str(val1_list[k]))
        text = text.replace("E2E", str(val4_list[k]))
        text = text.replace("E3E", str(val5_list[k]))
        text = text.replace("E4E", str(val6_list[k]))
        text = text.replace("E5E", str(val7_list[k]).split('.')[0])
        text = text.replace("E6E", str(val8_list[k]))
        text = text.replace("E7E", str(val9_list[k]))
        table_list = table_list + text

    text = """
            <tr>
               <td colspan="4" style="text-align: right">合计：</td>
               <td>R1R</td>
               <td>R2R</td>
               <td>R3R</td>
            </tr>
        """
    text = text.replace("R1R", str(int(sum(val7_list))).split('.')[0])
    text = text.replace("R2R", str(round(sum(val8_list), 2)))
    text = text.replace("R3R", str(round(sum(val9_list), 2)))
    table_list = table_list + text

    framework = str(framework).replace("ZBGMXD", table_list)
    tt = str(datetime.now().strftime("%Y-%m-%d %H%M%S%f"))  # 添加微秒信息确保唯一性
    # 保存生成的文件到指定目录
    output_file_path = os.path.join(output_directory, f"单据{new_order_number}_{tt}.html")  # 包含订单号确保唯一性
    with open(output_file_path, "w", encoding="utf-8") as file:
        file.write(framework)
    # 返回生成的文件路径
    return output_file_path


if __name__ == '__main__':
    start()