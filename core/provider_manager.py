"""
API 供应商管理器
负责：加载 api_providers.yaml -> 检测可用性 -> 获取模型列表 -> 用户选择
"""
import os
import json
import yaml
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class Provider:
    """API 供应商"""
    name: str
    type: str              # "ollama" 或 "openai_compatible"
    base_url: str
    api_key: str = ""
    models: List[str] = field(default_factory=list)
    auto_discover: bool = False
    available: bool = False  # 运行时检测结果
    resolved_models: List[str] = field(default_factory=list)  # 检测后实际可用模型


def load_providers(config_path: str = None) -> List[Provider]:
    """从 api_providers.yaml 加载供应商列表"""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "api_providers.yaml"
        )

    if not os.path.isfile(config_path):
        return []

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    providers = []
    for item in data.get("providers", []):
        providers.append(Provider(
            name=item.get("name", "Unknown"),
            type=item.get("type", "openai_compatible"),
            base_url=item.get("base_url", ""),
            api_key=item.get("api_key", ""),
            models=item.get("models", []),
            auto_discover=item.get("auto_discover", False),
        ))

    return providers


def discover_ollama_models(base_url: str, timeout: int = 5) -> List[str]:
    """获取 Ollama 本地已下载的模型列表"""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def discover_openai_models(base_url: str, api_key: str = "", timeout: int = 10) -> List[str]:
    """获取 OpenAI 兼容 API 的模型列表"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(f"{base_url}/models", headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []


def probe_provider(provider: Provider, timeout: int = 10) -> Tuple[bool, List[str]]:
    """
    检测供应商是否可用，返回 (是否可用, 模型列表)
    同时自动发现模型（如果 auto_discover=True）
    """
    models = list(provider.models)  # 复制配置中的模型

    if provider.auto_discover:
        if provider.type == "ollama":
            discovered = discover_ollama_models(provider.base_url, timeout)
            if discovered:
                # 合并去重：自动发现的在前面
                seen = set(models)
                for m in discovered:
                    if m not in seen:
                        models.insert(0, m)
                        seen.add(m)
        else:
            discovered = discover_openai_models(provider.base_url, provider.api_key, timeout)
            if discovered:
                seen = set(models)
                for m in discovered:
                    if m not in seen:
                        models.insert(0, m)
                        seen.add(m)

    if not models:
        return False, []

    # 选取第一个模型做连通性测试
    test_model = models[0]
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    if provider.type == "ollama":
        url = f"{provider.base_url}/api/chat"
        payload = {
            "model": test_model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }
    else:
        url = f"{provider.base_url}/chat/completions"
        payload = {
            "model": test_model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        # 尝试解析响应（可能返回空body或非JSON）
        try:
            resp.json()
        except (json.JSONDecodeError, ValueError):
            # 响应体为空或非JSON，保留已知模型列表，仅标记不可用
            return False, models

        if resp.status_code == 200:
            return True, models
        # 连接失败时保留已知模型列表（用于显示），仅标记为不可用
        return False, models
    except requests.exceptions.Timeout:
        # 超时时保留已知模型列表
        return False, models
    except requests.exceptions.ConnectionError:
        # 连接被拒绝时保留已知模型列表
        return False, models
    except Exception:
        # 其他异常也保留已知模型列表
        return False, models


def detect_available_providers(providers: List[Provider] = None) -> List[Provider]:
    """
    检测所有供应商的可用性，返回可用列表（含实际模型）
    """
    if providers is None:
        providers = load_providers()

    print("\n正在检测 API 供应商可用性...\n")
    available = []

    for p in providers:
        ok, models = probe_provider(p)
        p.available = ok
        p.resolved_models = models

        status = "可用" if ok else "不可用"
        model_count = len(models)
        print(f"  [{('+' if ok else '-')}] {p.name} - {model_count} 个模型 - {status}")

    available = [p for p in providers if p.available]
    print(f"\n共 {len(available)}/{len(providers)} 个供应商可用")

    return available


def user_select_model(providers: List[Provider]) -> Optional[Dict]:
    """
    交互式让用户选择模型
    返回 {"name": str, "base_url": str, "api_key": str, "model": str} 或 None
    """
    if not providers:
        print("没有可用的 API 供应商！请检查 api_providers.yaml 或网络连接。")
        return None

    # 构建模型选项：[(序号, 供应商名, 模型名, provider)]
    options = []
    idx = 1
    for p in providers:
        for m in p.resolved_models:
            options.append((idx, p.name, m, p))
            idx += 1

    # 显示列表
    print("\n" + "=" * 60)
    print("可用模型列表")
    print("=" * 60)

    current_provider = ""
    for num, prov_name, model_name, _ in options:
        if prov_name != current_provider:
            current_provider = prov_name
            print(f"\n  [{prov_name}]")
        print(f"    {num}. {model_name}")

    print("\n" + "-" * 60)
    print(f"  0. 退出")
    print("=" * 60)

    # 用户选择
    while True:
        try:
            choice = input("\n请选择模型编号: ").strip()
            if choice == "0":
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                _, prov_name, model_name, provider = options[choice_num - 1]
                result = {
                    "provider": prov_name,
                    "base_url": provider.base_url,
                    "api_key": provider.api_key,
                    "model": model_name,
                }
                print(f"\n已选择: {prov_name} / {model_name}")
                return result
            else:
                print(f"请输入 0-{len(options)} 之间的数字")
        except (ValueError, EOFError):
            print("请输入有效数字")


def get_all_available_models(providers: List[Provider] = None) -> List[Dict]:
    """
    获取所有可用模型的扁平列表（供 Web UI 使用）
    返回 [{"provider": str, "model": str, "base_url": str, "api_key": str, "label": str}, ...]
    """
    if providers is None:
        providers = load_providers()

    result = []
    for p in providers:
        ok, models = probe_provider(p)
        if ok:
            for m in models:
                result.append({
                    "provider": p.name,
                    "model": m,
                    "base_url": p.base_url,
                    "api_key": p.api_key,
                    "label": f"[{p.name}] {m}",
                })

    return result
