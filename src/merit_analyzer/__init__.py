from pathlib import Path

from dotenv import load_dotenv

from .processors.clustering import cluster_failures
from .interface.cli import CLIApplication

__all__ = ["cluster_failures", "CLIApplication"]

def main() -> None:
    load_dotenv(Path.cwd() / ".env")
    CLIApplication().run()
