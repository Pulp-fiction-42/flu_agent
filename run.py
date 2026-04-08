#!/usr/bin/env python3
"""
FluAgent 启动入口
支持多种模式：CLI / Web / API
参考 POPGENAGENT 的 run.py 设计
"""
import argparse
import sys
import os

# 添加技能目录到路径
skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, skill_dir)


def run_cli(model_override: str = None):
    """命令行 REPL 模式"""
    from core.agent import FluAgent
    from core.provider_manager import detect_available_providers, user_select_model

    print("=" * 50)
    print("FluAgent - 生物信息学分析助手")
    print("=" * 50)

    # 确定模型配置
    selected = None
    if model_override:
        # --model 参数指定，使用 config.yaml 中的配置
        selected = None
    else:
        # 自动检测并让用户选择
        providers = detect_available_providers()
        selected = user_select_model(providers)

    # 构建 Agent 参数
    agent_kwargs = {}
    if selected:
        agent_kwargs["model"] = selected["model"]
        # 临时覆盖 LLM 配置
        agent_kwargs["_base_url"] = selected["base_url"]
        agent_kwargs["_api_key"] = selected["api_key"]

    print("输入您的分析需求，输入 'quit' 或 'exit' 退出")
    print()

    agent = FluAgent(**agent_kwargs)

    while True:
        try:
            user_input = input("\n用户> ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                # 退出前询问是否保存
                if agent.pending_save:
                    save_choice = input("\n是否保存本次会话内容到 reports 目录? (y/n): ").strip().lower()
                    if save_choice == "y":
                        filepath = agent.save_pending()
                        if filepath:
                            print(f"✅ 已保存到: {filepath}")
                        else:
                            print("❌ 保存失败")
                print("再见!")
                break

            if not user_input:
                continue

            response = agent.chat(user_input)
            print(f"\nFluAgent> {response}")

        except KeyboardInterrupt:
            print("\n\n退出...")
            # 退出前询问是否保存
            if agent.pending_save:
                save_choice = input("\n是否保存本次会话内容到 reports 目录? (y/n): ").strip().lower()
                if save_choice == "y":
                    filepath = agent.save_pending()
                    if filepath:
                        print(f"✅ 已保存到: {filepath}")
                    else:
                        print("❌ 保存失败")
            break
        except Exception as e:
            print(f"错误: {e}")


def run_web(share: bool = False, debug: bool = False, port: int = 7860, use_ngrok: bool = False):
    """Web UI 模式"""
    from web.app import launch_web

    print(f"启动 Web 服务: http://localhost:{port}")
    launch_web(share=share, debug=debug, port=port, use_ngrok=use_ngrok)


def main():
    parser = argparse.ArgumentParser(description="FluAgent 启动器")
    parser.add_argument(
        "--mode", 
        choices=["cli", "web", "api"], 
        default="cli",
        help="运行模式: cli (命令行), web (Web界面), api (API服务)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=7861,
        help="Web/API 端口 (默认: 7861)"
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="创建 Gradio 分享链接 (临时链接)"
    )
    parser.add_argument(
        "--ngrok",
        action="store_true",
        help="使用 ngrok 暴露公网访问 (需先安装 pyngrok 并配置)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="开启调试模式"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="指定 LLM 模型"
    )
    
    args = parser.parse_args()
    
    if args.mode == "cli":
        run_cli(model_override=args.model)
    elif args.mode == "web":
        run_web(share=args.share, debug=args.debug, port=args.port, use_ngrok=args.ngrok)
    elif args.mode == "api":
        # 启动 FastAPI API 服务
        import uvicorn
        from api.main import app
        print(f"启动 API 服务: http://localhost:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
