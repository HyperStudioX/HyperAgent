"""Security validator for skill source code."""

import ast
import hashlib
from typing import Any


class SkillCodeValidator:
    """Validates skill source code for security concerns."""

    # Allowed imports for skills
    ALLOWED_IMPORTS = {
        "langgraph.graph",
        "langgraph.prebuilt",
        "langchain_core.messages",
        "langchain_core.prompts",
        "langchain_core.output_parsers",
        "pydantic",
        "typing",
        "datetime",
        "json",
        "re",
        "app.agents.skills.skill_base",
        "app.agents.tools",
        "app.agents.events",
        "app.ai.llm",
        "app.services.search_service",
        "app.services.image_generation",
    }

    # Forbidden names and operations
    FORBIDDEN_NAMES = {
        "eval",
        "exec",
        "compile",
        "open",
        "file",
        "__import__",
        "globals",
        "locals",
        "vars",
        "delattr",
        "setattr",
        "getattr",
        "hasattr",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
        "license",
        "copyright",
        "credits",
    }

    # Forbidden attribute access patterns (dunder methods that could be exploited)
    FORBIDDEN_ATTRIBUTES = {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__import__",
        "__reduce__",
        "__reduce_ex__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
    }

    # Forbidden modules that could be used for system access
    FORBIDDEN_MODULES = {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "pathlib",
        "importlib",
        "pickle",
        "shelve",
        "socket",
        "urllib",
        "requests",
        "http",
        "ftplib",
        "telnetlib",
        "xmlrpc",
    }

    def validate(self, source_code: str) -> tuple[bool, str]:
        """Validate skill source code for security issues.

        Args:
            source_code: Python source code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Parse source code
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check for forbidden operations
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_allowed_import(alias.name):
                        return False, f"Forbidden import: {alias.name}"

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if not self._is_allowed_import(module):
                    return False, f"Forbidden import: {module}"

            # Check for forbidden names
            elif isinstance(node, ast.Name):
                if node.id in self.FORBIDDEN_NAMES:
                    return False, f"Forbidden operation: {node.id}"

            # Check for dangerous function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_NAMES:
                        return False, f"Forbidden function call: {node.func.id}"

            # Check for forbidden attribute access (e.g., obj.__class__.__bases__)
            elif isinstance(node, ast.Attribute):
                if node.attr in self.FORBIDDEN_ATTRIBUTES:
                    return False, f"Forbidden attribute access: {node.attr}"

            # Check for file operations
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        if isinstance(item.context_expr.func, ast.Name):
                            if item.context_expr.func.id == "open":
                                return False, "Forbidden file operation: open()"

        # Verify skill class exists
        if not self._has_skill_class(tree):
            return (
                False,
                "Source code must define a skill class inheriting from Skill",
            )

        return True, ""

    def _is_allowed_import(self, module_name: str) -> bool:
        """Check if a module import is allowed.

        Args:
            module_name: Full module name (e.g., "os.path")

        Returns:
            True if allowed, False otherwise
        """
        # Check if module is in forbidden list
        root_module = module_name.split(".")[0]
        if root_module in self.FORBIDDEN_MODULES:
            return False

        # Check if module is in allowed list
        for allowed in self.ALLOWED_IMPORTS:
            if module_name == allowed or module_name.startswith(allowed + "."):
                return True

        return False

    def _has_skill_class(self, tree: ast.AST) -> bool:
        """Check if source code defines a Skill subclass.

        Args:
            tree: AST tree to check

        Returns:
            True if a Skill subclass is defined
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has Skill as a base
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Skill":
                        return True
        return False

    @staticmethod
    def compute_hash(source_code: str) -> str:
        """Compute SHA-256 hash of source code.

        Args:
            source_code: Source code to hash

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(source_code.encode()).hexdigest()

    def validate_and_hash(self, source_code: str) -> tuple[bool, str, str]:
        """Validate source code and compute its hash.

        Args:
            source_code: Source code to validate

        Returns:
            Tuple of (is_valid, error_message, hash)
        """
        is_valid, error = self.validate(source_code)
        code_hash = self.compute_hash(source_code) if is_valid else ""
        return is_valid, error, code_hash


# Global singleton
skill_code_validator = SkillCodeValidator()
