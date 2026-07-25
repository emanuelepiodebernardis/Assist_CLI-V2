
from pathlib import Path

import yaml


class UnknownCommandError(Exception):
    pass


class Registry:

    def __init__(self) -> None:

        registry_path = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "registry.yaml"
        )

        with open(
            registry_path,
            encoding="utf-8",
        ) as file:

            self.data = yaml.safe_load(file)

    def resolve(
        self,
        command: str,
    ) -> tuple[str, list[str]]:

        tasks = self.data.get(
            "tasks",
            {},
        )

        if command not in tasks:
            raise UnknownCommandError(
                f"Unknown command: {command}"
            )

        task_config = tasks[command]

        agent = task_config["agent"]

        skills = task_config["skills"]

        return agent, skills