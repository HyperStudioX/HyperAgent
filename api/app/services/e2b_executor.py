"""E2B Sandbox Service

Provides a unified interface for executing code in E2B sandboxes.
Supports multiple programming languages, file uploads, and visualization capture.
"""

import base64
from typing import Any, Literal
from io import BytesIO

from e2b import AsyncSandbox

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class E2BSandboxExecutor:
    """Manages E2B sandbox creation, file uploads, and code execution."""

    def __init__(
        self,
        api_key: str | None = None,
        template_id: str | None = None,
        timeout: int = 300,
    ):
        """Initialize E2B executor.

        Args:
            api_key: E2B API key (defaults to settings.e2b_api_key)
            template_id: Custom E2B template ID (defaults to settings.e2b_template_id)
            timeout: Sandbox timeout in seconds
        """
        self.api_key = api_key or settings.e2b_api_key
        self.template_id = template_id or (settings.e2b_template_id if hasattr(settings, 'e2b_template_id') else None)
        self.timeout = timeout
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

        self.sandbox = await AsyncSandbox.create(**sandbox_kwargs)
        logger.info("e2b_sandbox_created", sandbox_id=self.sandbox.sandbox_id)

        return self.sandbox.sandbox_id

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

    def _inject_python_imports(self, code: str) -> str:
        """Inject common Python imports if not present in the code.

        This helps prevent NameError when the LLM generates code that uses
        common libraries (plt, pd, np, sns) without importing them.

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
            "plt.": "import matplotlib.pyplot as plt",
            "matplotlib.": "import matplotlib.pyplot as plt",
            "sns.": "import seaborn as sns",
            "seaborn.": "import seaborn as sns",
        }

        missing_imports = []

        for usage, import_statement in import_mappings.items():
            # Check if the usage exists in code but import is missing
            if usage in code and import_statement not in code:
                # Also check for variations like "import pandas" without alias
                base_module = import_statement.split()[1]
                if f"import {base_module}" not in code and f"from {base_module}" not in code:
                    if import_statement not in missing_imports:
                        missing_imports.append(import_statement)

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
    ) -> dict[str, Any]:
        """Execute code in the sandbox.

        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout in seconds

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
            script_path = "/home/user/script.py"
            # Inject common imports if not present for Python data analysis
            code = self._inject_python_imports(code)
            await self.sandbox.files.write(script_path, code)
            cmd = f"python3 {script_path}"
        elif language in ("javascript", "js"):
            script_path = "/home/user/script.js"
            await self.sandbox.files.write(script_path, code)
            cmd = f"node {script_path}"
        elif language in ("typescript", "ts"):
            script_path = "/home/user/script.ts"
            await self.sandbox.files.write(script_path, code)
            # Install ts-node if needed
            await self.sandbox.commands.run(
                "npm install -g ts-node typescript 2>/dev/null || true",
                timeout=60,
            )
            cmd = f"ts-node {script_path}"
        elif language in ("bash", "sh", "shell"):
            script_path = "/home/user/script.sh"
            await self.sandbox.files.write(script_path, code)
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

    async def capture_visualizations(
        self,
        max_files: int = 10,
    ) -> list[dict[str, str]]:
        """Capture visualization files from sandbox.

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

        visualizations = []

        # Try to capture PNG outputs
        png_files = ["/tmp/output.png"] + [f"/tmp/output_{i}.png" for i in range(max_files)]
        for png_path in png_files:
            try:
                png_content = await self.sandbox.files.read(png_path)
                if png_content:
                    visualization_data = base64.b64encode(png_content).decode("utf-8")
                    visualizations.append({
                        "data": visualization_data,
                        "type": "image/png",
                        "path": png_path,
                    })
                    logger.info("visualization_captured", type="png", path=png_path, size=len(png_content))
            except Exception as e:
                # Only log for primary output file
                if png_path == "/tmp/output.png":
                    logger.debug("visualization_file_not_found", path=png_path, error=str(e))
                break  # Stop after first missing numbered file

        # Try to capture HTML outputs
        html_files = ["/tmp/output.html"] + [f"/tmp/output_{i}.html" for i in range(max_files)]
        for html_path in html_files:
            try:
                html_content = await self.sandbox.files.read(html_path)
                if html_content:
                    visualization_data = html_content.decode("utf-8") if isinstance(html_content, bytes) else html_content
                    visualizations.append({
                        "data": visualization_data,
                        "type": "text/html",
                        "path": html_path,
                    })
                    logger.info("visualization_captured", type="html", path=html_path, size=len(html_content))
            except Exception as e:
                # Only log for primary output file
                if html_path == "/tmp/output.html":
                    logger.debug("visualization_file_not_found", path=html_path, error=str(e))
                break  # Stop after first missing numbered file

        if visualizations:
            logger.info("total_visualizations_captured", count=len(visualizations))
        else:
            logger.debug("no_visualizations_found")

        return visualizations

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
    capture_viz: bool = True,
) -> dict[str, Any]:
    """Execute Python code with data files and optional package installation.

    Args:
        code: Python code to execute
        files: Dict of {filename: file_data} to upload
        packages: List of pip packages to install
        capture_viz: Whether to capture visualizations

    Returns:
        Dict with keys:
            - success: bool
            - stdout: str
            - stderr: str
            - exit_code: int
            - visualizations: list[dict] (if capture_viz=True)
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

        # Capture visualizations if requested
        if capture_viz:
            visualizations = await executor.capture_visualizations()
            result["visualizations"] = visualizations

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
