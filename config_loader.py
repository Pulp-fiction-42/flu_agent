"""
配置加载器
参考 POPGENAGENT 的 config_loader.py
支持从 YAML 文件加载配置，支持环境变量覆盖
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


# 默认配置文件路径
DEFAULT_CONFIG_FILE = "config.yaml"


@dataclass
class LLMConfig:
    """LLM 配置"""
    base_url: str = "https://apis.iflow.cn/v1"
    model: str = "qwen3-32b"
    api_key: str = "sk-a53bc75d6a2003fc593689e7e9cfbcfe"
    temperature: float = 0.7
    timeout: int = 800
    max_tokens: int = 4096


@dataclass
class PathsConfig:
    """路径配置"""
    tools_dir: str = "tools"
    knowledge_dir: str = "knowledge"
    workflow_dir: str = "workflow"
    data_dir: str = "data"
    reports_dir: str = "reports"
    example_dir: str = "example"


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_tool_rounds: int = 10
    enable_planner: bool = True
    planner_threshold: int = 2
    default_threads: int = 4
    command_timeout: int = 600


@dataclass
class WebConfig:
    """Web UI 配置"""
    enable: bool = False
    port: int = 7860
    share: bool = False
    debug: bool = False


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "sqlite"
    path: str = "data/sessions/bioagent.db"


@dataclass
class SearchConfig:
    """搜索配置"""
    enable: bool = True
    timeout: int = 30
    max_results: int = 5


@dataclass
class TextConfig:
    """文本处理配置"""
    enable: bool = True
    max_length: int = 5000
    pdf_library: str = "pypdf2"


@dataclass
class KnowledgeConfig:
    """知识库配置"""
    enable: bool = True
    vitaldb_enable: bool = True
    user_upload_dir: str = "knowledge/user_uploaded"
    search_fallback: bool = True


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "bioagent.log"


@dataclass
class MultiAgentAskConfig:
    """Ask Agent 配置"""
    max_rounds: int = 3


@dataclass
class MultiAgentPlanConfig:
    """Plan Agent 配置"""
    validate_dataflow: bool = True


@dataclass
class MultiAgentCraftConfig:
    """Craft Agent 配置"""
    max_tool_rounds: int = 10
    retry_on_fail: bool = True


@dataclass
class MultiAgentConfig:
    """多角色 Agent 配置"""
    enable: bool = False
    calibration_enable: bool = True
    ask: MultiAgentAskConfig = field(default_factory=MultiAgentAskConfig)
    plan: MultiAgentPlanConfig = field(default_factory=MultiAgentPlanConfig)
    craft: MultiAgentCraftConfig = field(default_factory=MultiAgentCraftConfig)


@dataclass
class DockerConfig:
    """Docker 容器化配置 (V2)"""
    enable: bool = False
    base_dir: str = "/tmp/fluagent/docker"
    timeout: int = 3600
    auto_pull: bool = True


@dataclass
class NextflowConfig:
    """Nextflow 配置 (V2)"""
    enable: bool = False
    templates_dir: str = "workflow/templates"
    work_dir: str = "/tmp/fluagent/nextflow"


@dataclass
class MultiuserConfig:
    """多用户配置 (V2)"""
    enable: bool = False
    session_timeout: int = 3600


@dataclass
class TaskQueueConfig:
    """任务队列配置 (V3)"""
    enable: bool = True
    backend: str = "celery"  # celery 或 memory
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"


@dataclass
class Config:
    """全局配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    tools: Dict[str, str] = field(default_factory=dict)
    agent: AgentConfig = field(default_factory=AgentConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    text: TextConfig = field(default_factory=TextConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    multi_agent: MultiAgentConfig = field(default_factory=MultiAgentConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)  # V2
    nextflow: NextflowConfig = field(default_factory=NextflowConfig)  # V2
    multiuser: MultiuserConfig = field(default_factory=MultiuserConfig)  # V2
    task_queue: TaskQueueConfig = field(default_factory=TaskQueueConfig)  # V3

    # 运行时属性（非配置文件）
    skill_dir: str = ""


class ConfigLoader:
    """配置加载器"""
    
    _instance: Optional[Config] = None
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or DEFAULT_CONFIG_FILE
    
    @classmethod
    def get_instance(cls, config_file: Optional[str] = None) -> Config:
        """获取配置单例"""
        if cls._instance is None:
            cls._instance = cls(config_file).load()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置单例（用于测试）"""
        cls._instance = None
    
    def load(self) -> Config:
        """加载配置文件"""
        # 查找配置文件
        config_path = self._find_config_file()
        
        if config_path and os.path.isfile(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        
        # 应用环境变量覆盖
        data = self._apply_env_overrides(data)
        
        # 构建配置对象
        return self._build_config(data, config_path)
    
    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        # 当前目录
        if os.path.isfile(self.config_file):
            return os.path.abspath(self.config_file)
        
        # 父目录
        parent = os.path.dirname(os.path.abspath(self.config_file))
        if os.path.isfile(os.path.join(parent, self.config_file)):
            return os.path.join(parent, self.config_file)
        
        # 技能目录
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_in_skill = os.path.join(skill_dir, self.config_file)
        if os.path.isfile(config_in_skill):
            return config_in_skill
        
        return None
    
    def _apply_env_overrides(self, data: Dict) -> Dict:
        """应用环境变量覆盖"""
        # LLM 配置
        if 'OLLAMA_BASE_URL' in os.environ:
            data.setdefault('llm', {})['base_url'] = os.environ['OLLAMA_BASE_URL']
        if 'OLLAMA_MODEL' in os.environ:
            data.setdefault('llm', {})['model'] = os.environ['OLLAMA_MODEL']
        
        return data
    
    def _build_config(self, data: Dict, config_path: Optional[str]) -> Config:
        """构建配置对象"""
        skill_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 解析路径
        paths_data = data.get('paths', {})
        paths = PathsConfig(**paths_data) if paths_data else PathsConfig()
        
        # 确保绝对路径
        def resolve_path(p: str) -> str:
            if os.path.isabs(p):
                return p
            return os.path.join(skill_dir, p)
        
        # 解析多角色配置（嵌套结构）
        ma_data = data.get('multi_agent', {})
        multi_agent = MultiAgentConfig(
            enable=ma_data.get('enable', False) if isinstance(ma_data, dict) else False,
            calibration_enable=ma_data.get('calibration_enable', True) if isinstance(ma_data, dict) else True,
            ask=MultiAgentAskConfig(**ma_data.get('ask', {})) if isinstance(ma_data.get('ask'), dict) else MultiAgentAskConfig(),
            plan=MultiAgentPlanConfig(**ma_data.get('plan', {})) if isinstance(ma_data.get('plan'), dict) else MultiAgentPlanConfig(),
            craft=MultiAgentCraftConfig(**ma_data.get('craft', {})) if isinstance(ma_data.get('craft'), dict) else MultiAgentCraftConfig(),
        ) if isinstance(ma_data, dict) else MultiAgentConfig()

        # V2 新增配置
        docker = DockerConfig(**data.get('docker', {})) if isinstance(data.get('docker'), dict) else DockerConfig()
        nextflow = NextflowConfig(**data.get('nextflow', {})) if isinstance(data.get('nextflow'), dict) else NextflowConfig()
        multiuser = MultiuserConfig(**data.get('multiuser', {})) if isinstance(data.get('multiuser'), dict) else MultiuserConfig()
        task_queue = TaskQueueConfig(**data.get('task_queue', {})) if isinstance(data.get('task_queue'), dict) else TaskQueueConfig()

        config = Config(
            llm=LLMConfig(**data.get('llm', {})),
            paths=paths,
            tools=data.get('tools', {}),
            agent=AgentConfig(**data.get('agent', {})),
            web=WebConfig(**data.get('web', {})),
            database=DatabaseConfig(**data.get('database', {})),
            search=SearchConfig(**data.get('search', {})),
            text=TextConfig(**data.get('text', {})),
            knowledge=KnowledgeConfig(**data.get('knowledge', {})),
            logging=LoggingConfig(**data.get('logging', {})),
            multi_agent=multi_agent,
            docker=docker,  # V2
            nextflow=nextflow,  # V2
            multiuser=multiuser,  # V2
            task_queue=task_queue,  # V3
            skill_dir=skill_dir,
        )

        return config


def get_config() -> Config:
    """获取全局配置（快捷函数）"""
    return ConfigLoader.get_instance()


# 兼容旧代码：导出常用配置
def get_skill_dir() -> str:
    return get_config().skill_dir


def get_tools_dir() -> str:
    cfg = get_config()
    return os.path.join(cfg.skill_dir, cfg.paths.tools_dir)


def get_knowledge_dir() -> str:
    cfg = get_config()
    return os.path.join(cfg.skill_dir, cfg.paths.knowledge_dir)


def get_reports_dir() -> str:
    cfg = get_config()
    return os.path.join(cfg.skill_dir, cfg.paths.reports_dir)


def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置字典"""
    cfg = get_config()
    return {
        "base_url": cfg.llm.base_url,
        "model": cfg.llm.model,
        "api_key": cfg.llm.api_key,
        "temperature": cfg.llm.temperature,
        "timeout": cfg.llm.timeout,
        "max_tokens": cfg.llm.max_tokens,
    }
