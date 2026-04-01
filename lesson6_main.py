import pandas as pd
import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import traceback

# 【修改点】导入配置文件
import config

# ==========================================
# 功能函数区
# ==========================================

def setup_logging():
    """
    初始化日志系统，同时输出到文件和屏幕
    """
    # 【修改点】引用 config.LOG_CONFIG
    logger = logging.getLogger()
    # 将字符串级别转换为 logging 常量
    log_level = getattr(logging, config.LOG_CONFIG['level'], logging.INFO)
    logger.setLevel(log_level)

    if logger.handlers:
        return

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件 Handler
    file_handler = RotatingFileHandler(
        config.LOG_CONFIG['filename'],
        maxBytes=config.LOG_CONFIG['max_bytes'],
        backupCount=config.LOG_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def create_db_engine(db_config):
    """
    创建数据库连接引擎
    """
    connection_str = (
        f"mysql+pymysql://{db_config['username']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )
    try:
        logging.debug(f"正在尝试连接数据库: {db_config['host']}:{db_config['port']}")
        return sqlalchemy.create_engine(connection_str)
    except Exception as e:
        logging.error(f"数据库连接引擎创建失败: {e}")
        raise

def fetch_data_from_db():
    """
    从数据库执行 SQL 并获取原始数据
    """
    logging.info("[步骤 1/5] 正在从数据库读取并聚合数据...")
    
    sql_query = """
    SELECT 
        h.hero_id,              
        h.hero_name,            
        COUNT(*) AS total_games,
        SUM(r.is_win) AS wins,  
        AVG(r.is_win) AS win_rate_float 
    FROM 
        battle_record r
    JOIN 
        hero h ON r.hero_id = h.hero_id 
    GROUP BY 
        h.hero_id, h.hero_name   
    """
    
    engine = None
    try:
        # 【修改点】传入 config.DB_CONFIG
        engine = create_db_engine(config.DB_CONFIG)
        df = pd.read_sql(sql_query, engine)
        logging.debug(f"SQL执行成功，共获取 {len(df)} 条英雄记录")
        return df
    except SQLAlchemyError as e:
        logging.error(f"SQL执行出错: {e}")
        raise
    finally:
        if engine:
            engine.dispose()
            logging.debug("数据库连接已释放")

def clean_and_process_data(df_raw):
    """
    数据清洗与精加工
    """
    logging.info("[步骤 2/5] 正在进行数据清洗与计算...")
    
    df = df_raw.copy()
    df['胜率(%)'] = df['win_rate_float'].apply(lambda x: round(x * 100, 1))
    logging.debug("胜率百分比计算完成")

    df = df.rename(columns={
        'hero_name': '英雄名称',
        'total_games': '总场次',
        'wins': '胜场数'
    })

    # 【修改点】引用 config.ANALYSIS_CONFIG
    min_games = config.ANALYSIS_CONFIG['min_games_threshold']
    df_filtered = df[df['总场次'] >= min_games].sort_values(by='胜率(%)', ascending=False)
    logging.debug(f"数据筛选完成（场次 >= {min_games}），剩余 {len(df_filtered)} 位英雄")

    result_columns = ['英雄名称', '总场次', '胜场数', '胜率(%)']
    df_final = df_filtered[result_columns].reset_index(drop=True)
    
    return df_final

def export_results(df_final):
    """
    导出结果到 Excel
    """
    logging.info("[步骤 3/5] 正在导出 Excel 文件...")
    try:
        # 【修改点】引用 config.OUTPUT_CONFIG
        df_final.to_excel(
            config.OUTPUT_CONFIG['excel_path'], 
            index=False, 
            sheet_name=config.OUTPUT_CONFIG['sheet_name']
        )
        logging.info(f"Excel 导出成功: {config.OUTPUT_CONFIG['excel_path']}")
    except Exception as e:
        logging.error(f"Excel 导出失败: {e}")
        raise

def print_statistics(df_final):
    """
    打印并记录统计摘要
    """
    logging.info("[步骤 4/5] 正在生成统计摘要...")
    
    logging.info("\n" + "="*60)
    logging.info("📊 英雄胜率统计摘要")
    logging.info("="*60)
    
    total_heroes = len(df_final)
    logging.info(f"1. 登场英雄数 (场次>=30): {total_heroes} 位")
    
    if total_heroes > 0:
        avg_win_rate = df_final['胜率(%)'].mean()
        logging.info(f"2. 平均胜率: {avg_win_rate:.1f}%")
        
        top_hero = df_final.iloc[0]
        logging.info(f"3. 胜率最高英雄: {top_hero['英雄名称']} ({top_hero['胜率(%)']}%)")
    else:
        logging.warning("没有符合条件的英雄数据")
    
    logging.info("-" * 60)
    # 【修改点】引用 config.ANALYSIS_CONFIG
    logging.info(f"🏆 胜率排行榜 Top {config.ANALYSIS_CONFIG['top_n_display']}:")
    
    df_display = df_final.head(config.ANALYSIS_CONFIG['top_n_display']).copy()
    df_display.index = df_display.index + 1
    df_display.index.name = '排名'
    
    logging.info("\n" + df_display.to_string())
    logging.info("="*60)

# ==========================================
# 主程序入口
# ==========================================

def main_task():
    """
    主任务逻辑
    """
    logging.info("🚀 =============== 任务开始 ===============")
    try:
        df_raw = fetch_data_from_db()
        df_final = clean_and_process_data(df_raw)
        export_results(df_final)
        print_statistics(df_final)
        logging.info("[步骤 5/5] ✅ 任务全部完成！")
        
    except Exception as e:
        logging.error(f"❌ 任务执行发生严重错误: {e}")
        logging.error("详细错误堆栈:\n" + traceback.format_exc())

if __name__ == "__main__":
    setup_logging()
    logging.info("系统初始化中...")
    logging.info("启动预热：立即执行第一次任务...")
    main_task()
    
    scheduler = BlockingScheduler()
    
    # 【修改点】引用 config.SCHEDULER_CONFIG
    scheduler.add_job(
        main_task, 
        'interval', 
        minutes=config.SCHEDULER_CONFIG['interval_minutes'],
        id='hero_analysis_job',
        name='英雄胜率定时分析任务',
        misfire_grace_time=30
    )
    
    logging.info(f"定时任务已启动，间隔: {config.SCHEDULER_CONFIG['interval_minutes']} 分钟")
    logging.info("按 Ctrl+C 可退出程序\n")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("收到停止信号，调度器已关闭。")