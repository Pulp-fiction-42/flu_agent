#!/usr/bin/env python3
"""
BioAgent 管理脚本
参考 POPGENAGENT 的 manage.py 设计
"""
import argparse
import sys
import os
import shutil

# 添加技能目录到路径
skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, skill_dir)


def check_tools():
    """检查工具可用性"""
    from config_loader import get_config
    
    cfg = get_config()
    print("=" * 50)
    print("检查生信工具可用性")
    print("=" * 50)
    
    # 导入旧配置获取工具检测函数
    import config
    available = config.check_tool_availability()
    
    print(f"\n{'工具名':<15} {'状态':<10} {'路径'}")
    print("-" * 60)
    
    available_count = 0
    for name, path in available.items():
        status = "✓ 可用" if path else "✗ 不可用"
        if path:
            available_count += 1
        print(f"{name:<15} {status:<10} {path or '-'}")
    
    print(f"\n总计: {available_count}/{len(available)} 工具可用")
    
    if available_count < len(available) * 0.5:
        print("\n⚠️ 警告: 超过半数工具不可用，请检查环境配置")


def check_llm():
    """检查 LLM 连接"""
    from config_loader import get_config, get_llm_config
    
    cfg = get_config()
    llm_cfg = get_llm_config()
    
    print("=" * 50)
    print("检查 LLM 连接")
    print("=" * 50)
    print(f"URL: {llm_cfg['base_url']}")
    print(f"模型: {llm_cfg['model']}")
    
    import requests
    
    try:
        response = requests.get(f"{llm_cfg['base_url']}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"\n✓ LLM 服务正常")
            print(f"可用模型: {len(models)}")
            for m in models[:5]:
                print(f"  - {m.get('name', 'unknown')}")
            if len(models) > 5:
                print(f"  ... 还有 {len(models) - 5} 个模型")
            
            # 检查当前模型
            current_model = llm_cfg['model']
            model_names = [m.get('name', '') for m in models]
            if any(current_model in name for name in model_names):
                print(f"\n✓ 当前模型 '{current_model}' 可用")
            else:
                print(f"\n⚠️ 当前模型 '{current_model}' 不可用")
                if model_names:
                    print(f"建议使用: {model_names[0]}")
        else:
            print(f"\n✗ LLM 服务异常: HTTP {response.status_code}")
    except Exception as e:
        print(f"\n✗ 无法连接 LLM: {e}")


def init_db():
    """初始化数据库"""
    from core.memory import Memory
    from config_loader import get_config
    
    cfg = get_config()
    db_path = os.path.join(cfg.skill_dir, cfg.database.path)
    
    print("=" * 50)
    print("初始化数据库")
    print("=" * 50)
    print(f"数据库路径: {db_path}")
    
    memory = Memory(db_path)
    print("✓ 数据库初始化完成")


def list_sessions():
    """列出会话"""
    from core.memory import Memory
    from config_loader import get_config
    
    cfg = get_config()
    db_path = os.path.join(cfg.skill_dir, cfg.database.path)
    
    memory = Memory(db_path)
    sessions = memory.list_sessions()
    
    print("=" * 50)
    print("会话列表")
    print("=" * 50)
    
    if not sessions:
        print("暂无会话")
        return
    
    for s in sessions:
        print(f"\n会话ID: {s['session_id'][:8]}...")
        print(f"创建时间: {s['created_at']}")
        print(f"更新时间: {s['updated_at']}")


def clean_cache():
    """清理缓存"""
    from config_loader import get_config
    
    cfg = get_config()
    cache_dir = os.path.join(cfg.skill_dir, cfg.paths.data_dir, "cache")
    
    print("=" * 50)
    print("清理缓存")
    print("=" * 50)
    print(f"缓存目录: {cache_dir}")
    
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print("✓ 缓存已清理")
    else:
        print("缓存目录不存在")


def main():
    parser = argparse.ArgumentParser(description="BioAgent 管理工具")
    parser.add_argument(
        "command",
        choices=["check-tools", "check-llm", "init-db", "sessions", "clean-cache"],
        help="管理命令"
    )
    
    args = parser.parse_args()
    
    if args.command == "check-tools":
        check_tools()
    elif args.command == "check-llm":
        check_llm()
    elif args.command == "init-db":
        init_db()
    elif args.command == "sessions":
        list_sessions()
    elif args.command == "clean-cache":
        clean_cache()


if __name__ == "__main__":
    main()
