"""E2B Sandbox Service

Provides a unified interface for executing code in E2B sandboxes.
Supports multiple programming languages, file uploads, and image capture.
"""

import base64
from io import BytesIO
from typing import Any, Literal

from e2b import AsyncSandbox

from app.config import settings
from app.core.logging import get_logger
from app.middleware.circuit_breaker import CircuitBreakerOpen, get_e2b_breaker

logger = get_logger(__name__)


class E2BSandboxExecutor:
    """Manages E2B sandbox creation, file uploads, and code execution."""

    def __init__(
        self,
        api_key: str | None = None,
        template_id: str | None = None,
        timeout: int | None = None,
    ):
        """Initialize E2B executor.

        Args:
            api_key: E2B API key (defaults to settings.e2b_api_key)
            template_id: Custom E2B template ID (defaults to settings.e2b_template_id)
            timeout: Sandbox timeout in seconds (defaults to settings.e2b_code_timeout)
        """
        self.api_key = api_key or settings.e2b_api_key
        self.template_id = template_id or (settings.e2b_template_id if hasattr(settings, 'e2b_template_id') else None)
        self.timeout = timeout or settings.e2b_code_timeout
        self.sandbox: AsyncSandbox | None = None

    async def __aenter__(self):
        """Context manager entry - creates sandbox."""
        await self.create_sandbox()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleans up sandbox."""
        await self.cleanup()

    async def create_sandbox(self) -> str:
        """Create E2B sandbox.

        Returns:
            Sandbox ID

        Raises:
            ValueError: If API key not configured
            CircuitBreakerOpen: If E2B service is unavailable
        """
        if not self.api_key:
            raise ValueError("E2B API key not configured. Set E2B_API_KEY environment variable.")

        sandbox_kwargs = {
            "api_key": self.api_key,
            "timeout": self.timeout,
        }

        # Use custom template if configured (significantly faster startup)
        if self.template_id:
            sandbox_kwargs["template"] = self.template_id
            logger.info("using_e2b_template", template_id=self.template_id)

        breaker = get_e2b_breaker()

        try:
            async with breaker.call():
                self.sandbox = await AsyncSandbox.create(**sandbox_kwargs)
            logger.info("e2b_sandbox_created", sandbox_id=self.sandbox.sandbox_id)
            return self.sandbox.sandbox_id

        except CircuitBreakerOpen as e:
            logger.warning(
                "e2b_sandbox_circuit_open",
                service="e2b",
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error("e2b_sandbox_creation_failed", error=str(e))
            raise

    async def upload_file(
        self,
        file_data: BytesIO | bytes,
        filename: str,
    ) -> None:
        """Upload a file to the sandbox.

        Args:
            file_data: File content as BytesIO or bytes
            filename: Destination filename in sandbox

        Raises:
            RuntimeError: If sandbox not created
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        if isinstance(file_data, BytesIO):
            content = file_data.getvalue()
        else:
            content = file_data

        await self.sandbox.files.write(filename, content)
        logger.info("file_uploaded_to_sandbox", filename=filename, size=len(content))

    def _detect_required_packages(self, code: str) -> list[str]:
        """Detect Python packages required by the code.

        Analyzes import statements and usage patterns to determine which
        packages need to be installed.

        Args:
            code: Python code to analyze

        Returns:
            List of package names to install via pip
        """
        import re

        # Map import names to pip package names
        # (import name -> pip package name)
        package_mapping = {
            "matplotlib": "matplotlib",
            "pandas": "pandas",
            "numpy": "numpy",
            "seaborn": "seaborn",
            "sklearn": "scikit-learn",
            "scipy": "scipy",
            "plotly": "plotly",
            "PIL": "pillow",
            "cv2": "opencv-python",
            "torch": "torch",
            "tensorflow": "tensorflow",
            "keras": "keras",
            "requests": "requests",
            "bs4": "beautifulsoup4",
            "lxml": "lxml",
            "yaml": "pyyaml",
            "dotenv": "python-dotenv",
            "flask": "flask",
            "fastapi": "fastapi",
            "sqlalchemy": "sqlalchemy",
            "psycopg2": "psycopg2-binary",
            "pymongo": "pymongo",
            "redis": "redis",
            "httpx": "httpx",
            "aiohttp": "aiohttp",
            "boto3": "boto3",
            "openpyxl": "openpyxl",
            "xlrd": "xlrd",
            "networkx": "networkx",
            "sympy": "sympy",
            "statsmodels": "statsmodels",
            "xgboost": "xgboost",
            "lightgbm": "lightgbm",
        }

        # Usage patterns that indicate a package is needed
        # (pattern -> pip package name)
        usage_patterns = {
            r"\bpd\.": "pandas",
            r"\bnp\.": "numpy",
            r"\bplt\.": "matplotlib",
            r"\bsns\.": "seaborn",
        }

        required_packages = set()

        # Check for explicit imports
        # Match: import foo, from foo import bar, import foo.bar
        import_pattern = r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        for match in re.finditer(import_pattern, code):
            module_name = match.group(1)
            if module_name in package_mapping:
                required_packages.add(package_mapping[module_name])

        # Check for usage patterns (handles cases where import is missing)
        for pattern, package in usage_patterns.items():
            if re.search(pattern, code):
                required_packages.add(package)

        return list(required_packages)

    def _inject_python_imports(self, code: str) -> str:
        """Inject common Python imports if not present in the code.

        This helps prevent NameError when the LLM generates code that uses
        common libraries (plt, pd, np, sns) without importing them.

        Also ensures matplotlib uses non-interactive backend for headless environments.

        Args:
            code: Original Python code

        Returns:
            Code with necessary imports prepended
        """
        # Common imports for data analysis
        import_mappings = {
            "pd.": "import pandas as pd",
            "pd,": "import pandas as pd",
            "pandas.": "import pandas as pd",
            "np.": "import numpy as np",
            "np,": "import numpy as np",
            "numpy.": "import numpy as np",
            "plt.": "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt",
            "matplotlib.": "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt",
            "sns.": "import seaborn as sns",
            "seaborn.": "import seaborn as sns",
        }

        missing_imports = []
        needs_matplotlib_backend = False

        for usage, import_statement in import_mappings.items():
            # Check if the usage exists in code but import is missing
            if usage in code and import_statement not in code:
                # Check if this is matplotlib-related
                if "matplotlib" in import_statement:
                    # Check if matplotlib backend is already configured
                    if "matplotlib.use" not in code and "matplotlib\nmatplotlib.use" not in "\n".join(missing_imports):
                        needs_matplotlib_backend = True
                        if import_statement not in missing_imports:
                            missing_imports.append(import_statement)
                else:
                    # For non-matplotlib imports, check variations
                    base_module = import_statement.split()[1]
                    if f"import {base_module}" not in code and f"from {base_module}" not in code:
                        if import_statement not in missing_imports:
                            missing_imports.append(import_statement)

        # If code already has matplotlib import but not backend, inject backend before it
        if ("import matplotlib" in code or "from matplotlib" in code) and "matplotlib.use" not in code:
            # Prepend backend setting
            backend_setup = "import matplotlib\nmatplotlib.use('Agg')\n\n"
            logger.info("injected_matplotlib_backend")
            code = backend_setup + code

        if missing_imports:
            imports_block = "\n".join(missing_imports) + "\n\n"
            logger.info("injected_python_imports", imports=missing_imports)
            return imports_block + code

        return code

    async def install_packages(
        self,
        packages: list[str],
        package_manager: Literal["pip", "npm"] = "pip",
        timeout: int = 120,
    ) -> tuple[bool, str, str]:
        """Install packages in the sandbox.

        Args:
            packages: List of package names to install
            package_manager: Package manager to use ("pip" or "npm")
            timeout: Installation timeout in seconds

        Returns:
            Tuple of (success, stdout, stderr)

        Raises:
            RuntimeError: If sandbox not created
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        if package_manager == "pip":
            packages_str = " ".join(packages)
            cmd = f"pip install -q {packages_str}"
        elif package_manager == "npm":
            packages_str = " ".join(packages)
            cmd = f"npm install -g {packages_str}"
        else:
            raise ValueError(f"Unsupported package manager: {package_manager}")

        logger.info("installing_packages", manager=package_manager, packages=packages)

        result = await self.sandbox.commands.run(cmd, timeout=timeout)

        success = result.exit_code == 0
        if success:
            logger.info("packages_installed", manager=package_manager, count=len(packages))
        else:
            logger.warning(
                "package_installation_failed",
                manager=package_manager,
                exit_code=result.exit_code,
                stderr=result.stderr,
            )

        return success, result.stdout or "", result.stderr or ""

    async def execute_code(
        self,
        code: str,
        language: Literal["python", "javascript", "typescript", "bash"] = "python",
        timeout: int = 180,
        auto_install_packages: bool = True,
    ) -> dict[str, Any]:
        """Execute code in the sandbox.

        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout in seconds
            auto_install_packages: Whether to auto-detect and install required packages

        Returns:
            Dict with keys:
                - success: bool
                - stdout: str
                - stderr: str
                - exit_code: int

        Raises:
            RuntimeError: If sandbox not created
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # Write code to file and determine execution command
        # Use /home/user/ instead of /tmp/ to avoid permission issues
        if language in ("python", "py"):
            # Auto-detect and install required packages (if not using custom template)
            if auto_install_packages and not self.template_id:
                required_packages = self._detect_required_packages(code)
                if required_packages:
                    logger.info("auto_installing_packages", packages=required_packages)
                    success, stdout, stderr = await self.install_packages(
                        required_packages, package_manager="pip"
                    )
                    if not success:
                        logger.warning(
                            "auto_package_installation_warning",
                            packages=required_packages,
                            stderr=stderr[:500] if stderr else None,
                        )

            script_path = "/home/user/script.py"
            # Inject common imports if not present for Python data analysis
            code = self._inject_python_imports(code)
            await self.sandbox.files.write(script_path, code.encode("utf-8"))
            cmd = f"python3 {script_path}"
        elif language in ("javascript", "js"):
            script_path = "/home/user/script.js"
            await self.sandbox.files.write(script_path, code.encode("utf-8"))
            cmd = f"node {script_path}"
        elif language in ("typescript", "ts"):
            script_path = "/home/user/script.ts"
            await self.sandbox.files.write(script_path, code.encode("utf-8"))
            # Install ts-node if needed
            await self.sandbox.commands.run(
                "npm install -g ts-node typescript 2>/dev/null || true",
                timeout=60,
            )
            cmd = f"ts-node {script_path}"
        elif language in ("bash", "sh", "shell"):
            script_path = "/home/user/script.sh"
            await self.sandbox.files.write(script_path, code.encode("utf-8"))
            await self.sandbox.commands.run("chmod +x /home/user/script.sh")
            cmd = script_path
        else:
            raise ValueError(f"Unsupported language: {language}")

        logger.info("executing_code", language=language, script_path=script_path)

        execution = await self.sandbox.commands.run(cmd, timeout=timeout)

        success = execution.exit_code == 0
        stdout = execution.stdout or ""
        stderr = execution.stderr or ""

        logger.info(
            "code_execution_completed",
            language=language,
            exit_code=execution.exit_code,
            success=success,
        )

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": execution.exit_code,
        }

    async def capture_images(
        self,
        max_files: int = 10,
    ) -> list[dict[str, str]]:
        """Capture image/output files from sandbox.

        Looks for:
        - /tmp/output.png, /tmp/output_0.png, /tmp/output_1.png, etc.
        - /tmp/output.html, /tmp/output_0.html, /tmp/output_1.html, etc.

        Args:
            max_files: Maximum number of numbered files to check

        Returns:
            List of dicts with keys:
                - data: str (base64 for PNG, HTML string for HTML)
                - type: str ("image/png" or "text/html")
                - path: str (original file path)

        Raises:
            RuntimeError: If sandbox not created
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        images = []

        # List files in /tmp for debugging
        try:
            list_result = await self.sandbox.commands.run("ls -la /tmp/output* 2>/dev/null || echo 'No output files found'", timeout=10)
            logger.info("tmp_output_files", stdout=list_result.stdout, stderr=list_result.stderr)
        except Exception as e:
            logger.debug("failed_to_list_tmp_files", error=str(e))

        # Helper function to try reading a file as bytes
        async def try_read_file(path: str, as_bytes: bool = True) -> bytes | str | None:
            try:
                if as_bytes:
                    # Read as bytes for binary files (PNG)
                    content = await self.sandbox.files.read(path, format="bytes")
                else:
                    # Read as text for HTML files
                    content = await self.sandbox.files.read(path, format="text")
                return content if content else None
            except Exception as e:
                logger.debug("image_file_not_found", path=path, error=str(e))
                return None

        # Try to capture PNG outputs
        # First check primary output file
        primary_png = await try_read_file("/tmp/output.png")
        if primary_png:
            image_data = base64.b64encode(primary_png).decode("utf-8")
            images.append({
                "data": image_data,
                "type": "image/png",
                "path": "/tmp/output.png",
            })
            logger.info("image_captured", type="png", path="/tmp/output.png", size=len(primary_png))

        # Then check numbered files (stop on first missing for efficiency)
        for i in range(max_files):
            png_path = f"/tmp/output_{i}.png"
            png_content = await try_read_file(png_path)
            if png_content:
                image_data = base64.b64encode(png_content).decode("utf-8")
                images.append({
                    "data": image_data,
                    "type": "image/png",
                    "path": png_path,
                })
                logger.info("image_captured", type="png", path=png_path, size=len(png_content))
            else:
                break  # Stop on first missing numbered file

        # Try to capture HTML outputs (read as text)
        # First check primary output file
        primary_html = await try_read_file("/tmp/output.html", as_bytes=False)
        if primary_html:
            images.append({
                "data": primary_html,
                "type": "text/html",
                "path": "/tmp/output.html",
            })
            logger.info("image_captured", type="html", path="/tmp/output.html", size=len(primary_html))

        # Then check numbered files (stop on first missing for efficiency)
        for i in range(max_files):
            html_path = f"/tmp/output_{i}.html"
            html_content = await try_read_file(html_path, as_bytes=False)
            if html_content:
                images.append({
                    "data": html_content,
                    "type": "text/html",
                    "path": html_path,
                })
                logger.info("image_captured", type="html", path=html_path, size=len(html_content))
            else:
                break  # Stop on first missing numbered file

        if images:
            logger.info("total_images_captured", count=len(images))
        else:
            logger.info("no_images_found_in_sandbox")

        return images

    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        if self.sandbox:
            try:
                await self.sandbox.kill()
                logger.info("sandbox_cleaned_up", sandbox_id=self.sandbox.sandbox_id)
            except Exception as e:
                logger.warning("sandbox_cleanup_failed", error=str(e))
            finally:
                self.sandbox = None


# Convenience functions for common use cases

async def execute_python_with_data(
    code: str,
    files: dict[str, BytesIO | bytes] | None = None,
    packages: list[str] | None = None,
    capture_images: bool = True,
) -> dict[str, Any]:
    """Execute Python code with data files and optional package installation.

    Args:
        code: Python code to execute
        files: Dict of {filename: file_data} to upload
        packages: List of pip packages to install
        capture_images: Whether to capture images/outputs

    Returns:
        Dict with keys:
            - success: bool
            - stdout: str
            - stderr: str
            - exit_code: int
            - images: list[dict] (if capture_images=True)
            - sandbox_id: str
    """
    async with E2BSandboxExecutor() as executor:
        # Upload files if provided
        if files:
            for filename, file_data in files.items():
                await executor.upload_file(file_data, filename)

        # Install packages if needed and not using template
        if packages and not executor.template_id:
            await executor.install_packages(packages, package_manager="pip")

        # Execute code
        result = await executor.execute_code(code, language="python")

        # Capture images if requested
        if capture_images:
            images = await executor.capture_images()
            result["images"] = images

        result["sandbox_id"] = executor.sandbox.sandbox_id if executor.sandbox else None

        return result


# Global singleton instance for reuse (optional)
_executor_instance: E2BSandboxExecutor | None = None


def get_e2b_executor() -> E2BSandboxExecutor:
    """Get or create global E2B executor instance.

    Note: Caller is responsible for creating/cleaning up sandbox.
    """
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = E2BSandboxExecutor()
    return _executor_instance
