import ast
import importlib.abc

from pathlib import Path
from types import ModuleType

from merit.core.assert_transformer import build_injected_globals, AssertRewriteTransformer


class MeritModuleLoader(importlib.abc.SourceLoader):
    """Custom loader for Merit test modules with AST transformations.
    
    This loader participates in Python's import protocol and handles
    AST transformation and injection of Merit-specific globals during
    module execution.
    """

    def __init__(self, fullname: str, path: Path) -> None:
        """Initialize the loader.
        
        Args:
            fullname: The fully qualified module name.
            path: Path to the module file.
        """
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname: str) -> str:
        return str(self.path)

    def get_data(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def exec_module(self, module: ModuleType) -> None:
        filename = self.get_filename(module.__name__)
        source = self.get_source(module.__name__)
        if source is None:
            msg = f"Cannot get source for module {module.__name__}"
            raise ImportError(msg)
        
        # Rewrite assertions to use the Merit-specific API.
        transformer = AssertRewriteTransformer(source, filename=filename)
        tree = ast.parse(source, filename=filename)
        transformed_tree = transformer.visit(tree)
        validated_tree = ast.fix_missing_locations(transformed_tree)

        code = compile(validated_tree, filename=filename, mode="exec")
        module.__dict__.update(build_injected_globals())
        exec(code, module.__dict__) 