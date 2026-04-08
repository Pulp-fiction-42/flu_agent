"""
全局配置文件

⚠️ 已迁移到 config.yaml + config_loader.py
此文件保留以确保向后兼容
"""
import os
import shutil

# 尝试导入新配置
try:
    from config_loader import get_config, get_llm_config
    _new_config_available = True
except ImportError:
    _new_config_available = False

# 如果新配置可用，使用新配置
if _new_config_available:
    cfg = get_config()
    
    # 导出配置项
    SKILL_DIR = cfg.skill_dir
    TOOLS_DIR = os.path.join(cfg.skill_dir, cfg.paths.tools_dir)
    KNOWLEDGE_DIR = os.path.join(cfg.skill_dir, cfg.paths.knowledge_dir)
    WORKFLOW_DIR = os.path.join(cfg.skill_dir, cfg.paths.workflow_dir)
    EXAMPLE_DIR = os.path.join(cfg.skill_dir, cfg.paths.example_dir)
    REPORTS_DIR = os.path.join(cfg.skill_dir, cfg.paths.reports_dir)
    
    OLLAMA_BASE_URL = cfg.llm.base_url
    DEFAULT_MODEL = cfg.llm.model
    TEMPERATURE = cfg.llm.temperature
    
    DEFAULT_THREADS = cfg.agent.default_threads
    DEFAULT_OUTPUT_FORMAT = "json"
    COMMAND_TIMEOUT = cfg.agent.command_timeout
    
    # 工具路径
    _tool_paths = cfg.tools
    
    def resolve_tool_path(primary: str, fallback: str = "") -> str:
        """解析工具路径"""
        if os.path.isfile(primary) and os.access(primary, os.X_OK):
            return primary
        if fallback and shutil.which(fallback):
            return shutil.which(fallback)
        cmd_name = os.path.basename(primary)
        found = shutil.which(cmd_name)
        if found:
            return found
        return primary
    
    # 🔧 为每个工具生成路径常量（如 SEQKIT_PATH, FASTP_PATH 等）
    for tool_name, tool_path in _tool_paths.items():
        const_name = f"{tool_name.upper()}_PATH"
        globals()[const_name] = resolve_tool_path(tool_path)
    
    def check_tool_availability() -> dict:
        """检测工具可用性"""
        available = {}
        for name, path in _tool_paths.items():
            resolved = resolve_tool_path(path)
            if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
                available[name] = resolved
            else:
                available[name] = None
        return available

else:
    # 旧配置（降级使用）
    SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
    TOOLS_DIR = os.path.join(SKILL_DIR, "tools")
    KNOWLEDGE_DIR = os.path.join(SKILL_DIR, "knowledge")
    WORKFLOW_DIR = os.path.join(SKILL_DIR, "workflow")
    EXAMPLE_DIR = os.path.join(SKILL_DIR, "example")
    REPORTS_DIR = os.path.join(SKILL_DIR, "reports")

    OLLAMA_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen3:4b"
    TEMPERATURE = 0.7

    DEFAULT_THREADS = 4
    DEFAULT_OUTPUT_FORMAT = "json"
    COMMAND_TIMEOUT = 600

    def resolve_tool_path(primary: str, fallback: str = "") -> str:
        if os.path.isfile(primary) and os.access(primary, os.X_OK):
            return primary
        if fallback and shutil.which(fallback):
            return shutil.which(fallback)
        cmd_name = os.path.basename(primary)
        found = shutil.which(cmd_name)
        if found:
            return found
        return primary

    def check_tool_availability() -> dict:
        return {}

# 确保目录存在
for _d in [REPORTS_DIR, WORKFLOW_DIR, EXAMPLE_DIR]:
    os.makedirs(_d, exist_ok=True)
