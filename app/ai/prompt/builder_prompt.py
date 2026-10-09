import os
import yaml


class BuilderPromptYaml:
    """YAML 提示词加载工具。"""
    @staticmethod
    def get_prompt(file_name: str) -> dict[str, str]:
        # 拼接 YAML 文件完整路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, file_name)
        # 加载 YAML 文件
        with open(file_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        return {
            "system_prompt": config["system_prompt"].strip(),
            "user_prompt": config["user_prompt"].strip(),
        }
