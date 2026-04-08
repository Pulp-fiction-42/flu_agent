"""
更新日志模块
记录 BioAgent 的所有更新和变更
"""
import os
import datetime
from typing import Optional


class Changelog:
    """更新日志管理器"""

    def __init__(self, changelog_path: str = None):
        if changelog_path is None:
            from config_loader import get_skill_dir
            self.changelog_path = os.path.join(get_skill_dir(), "CHANGELOG.md")
        else:
            self.changelog_path = changelog_path

    def _ensure_file(self):
        """确保更新日志文件存在"""
        if not os.path.exists(self.changelog_path):
            with open(self.changelog_path, 'w', encoding='utf-8') as f:
                f.write("# BioAgent 更新日志\n\n")
                f.write("## 更新格式\n\n")
                f.write("每个更新条目包含：\n")
                f.write("- 日期\n")
                f.write("- 更新类型 (新增/修改/修复)\n")
                f.write("- 更新描述\n\n")
                f.write("---\n\n")

    def add_entry(self, entry_type: str, description: str, author: str = "System"):
        """
        添加更新日志条目

        Args:
            entry_type: 更新类型 (新增/修改/修复/优化等)
            description: 更新描述
            author: 更新作者
        """
        self._ensure_file()

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_entry = f"## [{entry_type}] {timestamp} - {author}\n\n{description}\n\n---\n\n"

        # 读取现有内容
        with open(self.changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 在末尾插入新条目（在最后的 --- 之后）
        lines = content.split('\n')
        insert_idx = len(lines) - 1
        while insert_idx >= 0 and lines[insert_idx].strip() != '---':
            insert_idx -= 1

        if insert_idx >= 0:
            new_lines = lines[:insert_idx] + [new_entry.strip()] + lines[insert_idx:]
        else:
            new_lines = [new_entry] + lines

        with open(self.changelog_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

    def get_entries(self, limit: int = 10) -> list:
        """获取最近的更新日志条目"""
        if not os.path.exists(self.changelog_path):
            return []

        with open(self.changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 简单解析（每个 --- 分隔一个条目）
        entries = []
        blocks = content.split('---\n\n')

        for block in blocks[-limit:]:
            if block.strip() and block.strip() != "# BioAgent 更新日志" and block.strip() != "## 更新格式":
                entries.append(block.strip())

        return list(reversed(entries))

    def print_recent(self, limit: int = 5):
        """打印最近的更新日志"""
        entries = self.get_entries(limit)
        print("\n" + "=" * 50)
        print("最近更新:")
        print("=" * 50)
        for entry in entries:
            print(f"\n{entry}\n")


# 全局实例
_changelog: Optional[Changelog] = None


def get_changelog() -> Changelog:
    """获取更新日志管理器实例"""
    global _changelog
    if _changelog is None:
        _changelog = Changelog()
    return _changelog


def add_update(entry_type: str, description: str, author: str = "System"):
    """快捷函数：添加更新日志条目"""
    get_changelog().add_entry(entry_type, description, author)