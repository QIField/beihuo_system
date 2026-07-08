



import datetime




def for_test():
    print("="*100)
    print("for_test", datetime.datetime.now())
    print("="*100)

def test():
    from app.core.task_enhancer import get_task_manager
    task_manager=get_task_manager()
    try:
        task_manager.schedule(
            func=for_test,
            trigger='interval',
            job_id='test_task',
            seconds=1,
            next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=10),
            replace_existing=True
        )
        print("="*100)
        print("[测试] 定时任务已注册（每3秒执行）")
        print("="*100)

        from app.core.task_enhancer import register_task_config
        register_task_config(
            job_id='test_task',
            enabled=True,
            demand_driven=True,
            idle_timeout_seconds=30,
            description='测试任务（按需执行，10秒心跳）'
        )
        print("[测试] 看门狗配置已注册（按需执行模式）")

        # 创建后立即暂停，等待心跳触发
        job = task_manager._scheduler.get_job('test_task')
        if job:
            job.pause()
            print("[测试] 任务已暂停，等待心跳触发")

    except Exception as e:
        print(f"[测试] 注册失败: {e}")
