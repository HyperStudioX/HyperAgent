"""Browser automation tool for AI agents using browser-use library."""

import json
from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Browser-use will be imported dynamically to avoid hard dependency
try:
    from browser_use import Agent as BrowserAgent
    from browser_use import Browser, BrowserConfig
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    logger.warning("browser_use_not_installed", message="Install with: pip install browser-use")


class BrowserUseInput(BaseModel):
    """Input schema for browser use tool."""

    task: str = Field(
        description="The task to perform in the browser (e.g., 'Go to example.com and extract the main heading')"
    )
    headless: bool = Field(
        default=True,
        description="Run browser in headless mode (no GUI)",
    )
    max_steps: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of browser actions to take (1-50)",
    )


@tool(args_schema=BrowserUseInput)
async def browser_use(
    task: str,
    headless: bool = True,
    max_steps: int = 10,
) -> str:
    """Use a real browser to interact with websites, extract data, or perform web tasks.

    This tool provides browser automation capabilities including:
    - Navigate to websites
    - Click elements, fill forms, scroll pages
    - Extract text, tables, or structured data
    - Take screenshots
    - Handle dynamic content and JavaScript

    Use this when you need to:
    - Interact with dynamic websites that require JavaScript
    - Extract data from complex web applications
    - Automate web tasks that require clicking, typing, or navigation
    - Access content behind authentication or forms

    Args:
        task: Clear description of what to do in the browser
        headless: Run browser without GUI (default: True)
        max_steps: Maximum browser actions to take (default: 10)

    Returns:
        JSON string with browser task results
    """
    if not BROWSER_USE_AVAILABLE:
        error_msg = "Browser-use library not installed. Install with: pip install browser-use"
        logger.error("browser_use_unavailable")
        return json.dumps({
            "success": False,
            "error": error_msg,
            "task": task,
        })

    logger.info(
        "browser_use_tool_invoked",
        task=task[:100],
        headless=headless,
        max_steps=max_steps,
    )

    try:
        # Configure browser
        browser_config = BrowserConfig(
            headless=headless,
            disable_security=False,  # Keep security enabled
        )

        # Initialize browser
        browser = Browser(config=browser_config)

        # Create browser agent
        agent = BrowserAgent(
            task=task,
            llm=None,  # Will use default LLM from browser-use
            browser=browser,
            max_actions=max_steps,
        )

        # Execute the task
        result = await agent.run()

        # Close browser
        await browser.close()

        logger.info(
            "browser_use_completed",
            task=task[:50],
            success=True,
        )

        return json.dumps({
            "success": True,
            "result": str(result),
            "task": task,
        })

    except Exception as e:
        logger.error(
            "browser_use_failed",
            task=task[:50],
            error=str(e),
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "task": task,
        })


@tool
async def browser_navigate(url: str) -> str:
    """Navigate to a URL and extract the page content.

    A simpler browser tool for basic navigation and content extraction.
    Use this when you just need to fetch page content without complex interactions.

    Args:
        url: The URL to visit

    Returns:
        JSON string with page content
    """
    if not BROWSER_USE_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "Browser-use library not installed",
        })

    logger.info("browser_navigate_invoked", url=url)

    try:
        browser_config = BrowserConfig(headless=True)
        browser = Browser(config=browser_config)

        # Simple navigation task
        agent = BrowserAgent(
            task=f"Go to {url} and extract all visible text content",
            browser=browser,
            max_actions=3,
        )

        result = await agent.run()
        await browser.close()

        return json.dumps({
            "success": True,
            "url": url,
            "content": str(result),
        })

    except Exception as e:
        logger.error("browser_navigate_failed", url=url, error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
            "url": url,
        })
