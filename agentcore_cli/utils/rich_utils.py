"""Rich utilities for consistent CLI formatting and styling.

This module provides centralized Rich utilities for beautiful terminal output
without using progress bars (which can be glitchy).
"""

from rich.console import Console
from rich.table import Table
from rich.json import JSON
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.markdown import Markdown
from typing import Any
import json
import re


# Global console instance for consistent output
console = Console()


def print_success(message: str, details: str | None = None) -> None:
    """Print a success message with consistent styling."""
    text = Text("✅ ", style="green") + Text(message, style="green bold")
    console.print(text)
    if details:
        console.print(f"   {details}", style="dim")


def print_error(message: str, details: str | None = None) -> None:
    """Print an error message with consistent styling."""
    text = Text("❌ ", style="red") + Text(message, style="red bold")
    console.print(text)
    if details:
        console.print(f"   {details}", style="dim red")


def print_warning(message: str, details: str | None = None) -> None:
    """Print a warning message with consistent styling."""
    text = Text("⚠️  ", style="yellow") + Text(message, style="yellow bold")
    console.print(text)
    if details:
        console.print(f"   {details}", style="dim yellow")


def print_info(message: str, details: str | None = None) -> None:
    """Print an info message with consistent styling."""
    text = Text("💡 ", style="blue") + Text(message, style="blue bold")
    console.print(text)
    if details:
        console.print(f"   {details}", style="dim")


def print_step(step_number: int, message: str, details: str | None = None) -> None:
    """Print a step message with consistent styling."""
    text = Text(f"🔄 Step {step_number}: ", style="cyan") + Text(message, style="cyan bold")
    console.print(text)
    if details:
        console.print(f"   {details}", style="dim")


def print_section_header(title: str, emoji: str = "📋") -> None:
    """Print a section header with consistent styling."""
    text = Text(f"{emoji} ", style="bright_blue") + Text(title, style="bright_blue bold")
    console.print()
    console.print(text)


def is_markdown_content(text: str) -> bool:
    """Detect if text contains markdown formatting."""

    # Common markdown patterns
    markdown_patterns = [
        r"#{1,6}\s+",  # Headers
        r"\*\*.*?\*\*",  # Bold
        r"\*.*?\*",  # Italic
        r"`.*?`",  # Inline code
        r"```.*?```",  # Code blocks
        r"\[.*?\]\(.*?\)",  # Links
        r"^\s*[-*+]\s+",  # Lists
        r"^\s*\d+\.\s+",  # Numbered lists
        r"^\s*>\s+",  # Blockquotes
    ]

    return any(re.search(pattern, text, re.MULTILINE | re.DOTALL) for pattern in markdown_patterns)


def print_markdown(content: str, title: str | None = None) -> None:
    """Print markdown content with Rich rendering."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    markdown = Markdown(content)
    console.print(markdown)


def print_smart_content(content: str, title: str | None = None) -> None:
    """Intelligently print content as markdown or plain text."""
    if is_markdown_content(content):
        print_markdown(content, title)
    else:
        if title:
            console.print(f"\n[bold]{title}[/bold]")
        console.print(content)


def _find_markdown_fields(data: dict, path: str = "") -> dict[str, tuple[str, str]]:
    """Recursively find markdown content in nested dictionaries.

    Returns a dict of {field_path: (content, display_name)}
    """
    markdown_fields = ["content", "message", "text", "response", "output", "body", "description"]
    found_markdown = {}

    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, str) and key in markdown_fields and is_markdown_content(value):
            # Found markdown content
            display_name = current_path.replace(".", " → ").title()
            found_markdown[current_path] = (value, display_name)
        elif isinstance(value, dict):
            # Recursively search nested dictionaries
            nested_markdown = _find_markdown_fields(value, current_path)
            found_markdown.update(nested_markdown)

    return found_markdown


def _set_nested_value(data: dict, path: str, value: str) -> None:
    """Set a value in a nested dictionary using dot notation path."""
    keys = path.split(".")
    current = data

    for key in keys[:-1]:
        if key in current and isinstance(current[key], dict):
            current = current[key]
        else:
            return

    if keys[-1] in current:
        current[keys[-1]] = value


def print_json_with_markdown(
    data: dict | list | str, title: str | None = None, render_markdown_fields: bool = True
) -> None:
    """Print JSON data with automatic markdown rendering for text fields."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    try:
        # Handle string that might be JSON
        if isinstance(data, str):
            data = json.loads(data)

        if render_markdown_fields and isinstance(data, dict):
            # Find all markdown content recursively
            markdown_content = _find_markdown_fields(data)

            if markdown_content:
                # Print the JSON structure first (without markdown fields)
                display_data = json.loads(json.dumps(data))  # Deep copy

                for path, (content, display_name) in markdown_content.items():
                    _set_nested_value(display_data, path, "[Rendered as markdown below]")

                # Show JSON structure
                json_obj = JSON.from_data(display_data)
                console.print(json_obj)

                # Render markdown content separately
                for path, (content, display_name) in markdown_content.items():
                    console.print()
                    print_markdown(content, title=f"{display_name} (Markdown)")

                return

        # Default JSON rendering
        json_obj = JSON.from_data(data)
        console.print(json_obj)
    except (json.JSONDecodeError, TypeError):
        # If not valid JSON, try to render as markdown or plain text
        print_smart_content(str(data), title)


def print_json(data: dict | list | str, title: str | None = None) -> None:
    """Print JSON data with beautiful formatting (legacy function for backward compatibility)."""
    print_json_with_markdown(data, title, render_markdown_fields=False)


def print_agent_response(response: dict | str, title: str = "Agent Response") -> None:
    """Print agent response with intelligent markdown rendering."""
    print_json_with_markdown(response, title=title, render_markdown_fields=True)


def print_agent_response_raw(response: dict | str, title: str = "Agent Response") -> None:
    """Print agent response with markdown extracted but shown as raw text for clipboard usability."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    try:
        # Handle string that might be JSON
        if isinstance(response, str):
            data = json.loads(response)
        else:
            data = response

        if isinstance(data, dict):
            # Find all markdown content recursively
            markdown_content = _find_markdown_fields(data)

            if markdown_content:
                # Print the JSON structure first (without markdown fields)
                display_data = json.loads(json.dumps(data))  # Deep copy

                for path, (content, display_name) in markdown_content.items():
                    _set_nested_value(display_data, path, "[Raw markdown shown below]")

                # Show JSON structure
                json_obj = JSON.from_data(display_data)
                console.print(json_obj)

                # Show raw markdown content (not rendered)
                for path, (content, display_name) in markdown_content.items():
                    console.print()
                    console.print(f"[bold]{display_name} (Raw Markdown):[/bold]")
                    console.print("─" * (len(display_name) + 15))
                    console.print(content)

                return

        # Default JSON rendering if no markdown found
        json_obj = JSON.from_data(data)
        console.print(json_obj)
    except (json.JSONDecodeError, TypeError):
        # If not valid JSON, print as plain text
        console.print(str(response))


def extract_response_content(response: dict | str, prefer_markdown: bool = True) -> str:
    """Extract only the response content for piping (no formatting, headers, or JSON structure).

    Args:
        response: The response data (JSON string or dict)
        prefer_markdown: If True, return detected markdown content; if False, return full JSON

    Returns:
        The extracted content as a plain string
    """
    try:
        # Handle string that might be JSON
        if isinstance(response, str):
            data = json.loads(response)
        else:
            data = response

        if prefer_markdown and isinstance(data, dict):
            # Find all markdown content recursively
            markdown_content = _find_markdown_fields(data)

            if markdown_content:
                # Return all markdown content concatenated
                contents = []
                for path, (content, display_name) in markdown_content.items():
                    contents.append(content)
                return "\n\n".join(contents)

        # If no markdown found or prefer_markdown is False, return the JSON
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return str(data)

    except (json.JSONDecodeError, TypeError):
        # If not valid JSON, return as-is
        return str(response)


def create_table(
    title: str, columns: list[str], rows: list[list[str]], show_header: bool = True, show_lines: bool = False
) -> Table:
    """Create a Rich table with consistent styling."""
    table = Table(title=title, show_header=show_header, show_lines=show_lines)

    # Add columns
    for column in columns:
        table.add_column(column, style="cyan")

    # Add rows
    for row in rows:
        table.add_row(*row)

    return table


def print_table(
    title: str, columns: list[str], rows: list[list[str]], show_header: bool = True, show_lines: bool = False
) -> None:
    """Print a table with Rich formatting."""
    table = create_table(title, columns, rows, show_header, show_lines)
    console.print(table)


def print_section_block(content: str, title: str | None = None, style: str = "blue") -> None:
    """Print content in a simple block format (clipboard-friendly)."""
    if title:
        console.print(f"\n[{style} bold]{title}[/{style} bold]")
        console.print("─" * len(title), style=style)
    console.print(f"[{style}]{content}[/{style}]")


def print_key_value_pairs(pairs: dict[str, Any], title: str | None = None) -> None:
    """Print key-value pairs with consistent formatting."""
    if title:
        print_section_header(title)

    for key, value in pairs.items():
        # Mask sensitive values
        display_value = (
            "***"
            if any(sensitive in key.lower() for sensitive in ["key", "secret", "token", "password"])
            else str(value)
        )
        console.print(f"   {key}: [bold]{display_value}[/bold]")


def create_status_tree(title: str, items: dict[str, Any]) -> Tree:
    """Create a tree view for hierarchical status information."""
    tree = Tree(f"[bold blue]{title}[/bold blue]")

    for key, value in items.items():
        if isinstance(value, dict):
            branch = tree.add(f"[cyan]{key}[/cyan]")
            for sub_key, sub_value in value.items():
                branch.add(f"{sub_key}: [bold]{sub_value}[/bold]")
        elif isinstance(value, list):
            branch = tree.add(f"[cyan]{key}[/cyan]")
            for item in value:
                branch.add(f"• {item}")
        else:
            tree.add(f"[cyan]{key}[/cyan]: [bold]{value}[/bold]")

    return tree


def print_status_tree(title: str, items: dict[str, Any]) -> None:
    """Print a tree view for hierarchical status information."""
    tree = create_status_tree(title, items)
    console.print(tree)


def print_next_steps(steps: list[str]) -> None:
    """Print next steps with consistent formatting."""
    print_section_header("Next Steps", "🚀")
    for i, step in enumerate(steps, 1):
        console.print(f"   {i}. {step}")


def print_command_examples(examples: list[tuple[str, str]]) -> None:
    """Print command examples with syntax highlighting."""
    print_section_header("Examples", "💡")
    for command, description in examples:
        console.print(f"   • {description}:")
        console.print(f"     [bold cyan]{command}[/bold cyan]")


def print_ascii_banner(subtitle: str | None = None) -> None:
    """Print the main AgentCore CLI ASCII art banner."""
    try:
        from agentcore_cli.static.banner import banner_ascii

        console.print()
        console.print(f"[bright_blue]{banner_ascii}[/bright_blue]")
        if subtitle:
            console.print(f"[bright_blue bold]   {subtitle}[/bright_blue bold]")
        console.print()
    except ImportError:
        # Fallback if ASCII art can't be loaded
        print_banner("AgentCore CLI", subtitle, emoji="🚀")


def print_banner(title: str, subtitle: str | None = None, emoji: str = "🚀", use_ascii: bool = False) -> None:
    """Print an attractive banner for major sections (clipboard-friendly)."""
    console.print()

    if use_ascii:
        try:
            from agentcore_cli.static.banner import banner_ascii

            console.print(f"[bright_blue]{banner_ascii}[/bright_blue]")
            if subtitle:
                console.print(f"[bright_blue bold]   {subtitle}[/bright_blue bold]")
        except ImportError:
            # Fallback to regular banner if ASCII art can't be loaded
            banner_text = f"[bright_blue bold]{emoji} {title}[/bright_blue bold]"
            console.print(banner_text)
            if subtitle:
                console.print(f"[bright_blue]   {subtitle}[/bright_blue]")
    else:
        banner_text = f"[bright_blue bold]{emoji} {title}[/bright_blue bold]"
        console.print(banner_text)
        if subtitle:
            console.print(f"[bright_blue]   {subtitle}[/bright_blue]")
        console.print("═" * (len(title) + 3), style="bright_blue")

    console.print()


def print_summary_box(title: str, items: dict[str, str], style: str = "green") -> None:
    """Print a summary with key information (clipboard-friendly)."""
    console.print()
    console.print(f"[{style} bold]📋 {title}[/{style} bold]")
    console.print("─" * (len(title) + 3), style=style)

    for key, value in items.items():
        console.print(f"[bold]{key}:[/bold] {value}")
    console.print()


def format_file_syntax(file_path: str, content: str, language: str = "json") -> Syntax:
    """Create syntax-highlighted content for files."""
    return Syntax(content, language, theme="monokai", line_numbers=True)


def print_file_content(file_path: str, content: str, language: str = "json") -> None:
    """Print file content with syntax highlighting."""
    syntax = format_file_syntax(file_path, content, language)
    console.print(f"\n📄 [bold]{file_path}[/bold]")
    console.print(syntax)


def print_columns(items: list[str], title: str | None = None) -> None:
    """Print items in columns for compact display."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    columns = Columns(items, equal=True, expand=True)
    console.print(columns)


def print_copyable_value(label: str, value: str, description: str | None = None) -> None:
    """Print a value that users commonly need to copy (clipboard-friendly)."""
    console.print(f"[bold cyan]{label}:[/bold cyan] {value}")
    if description:
        console.print(f"   [dim]{description}[/dim]")


def print_copyable_values(values: dict[str, str], title: str | None = None) -> None:
    """Print multiple copyable values (clipboard-friendly)."""
    if title:
        print_section_header(title)

    for label, value in values.items():
        print_copyable_value(label, value)
    console.print()


def print_command(command: str, description: str | None = None) -> None:
    """Print a command that users can copy and run."""
    if description:
        console.print(f"[dim]{description}[/dim]")
    console.print(f"[bold green]$[/bold green] [cyan]{command}[/cyan]")


def print_commands(commands: list[tuple[str, str | None]], title: str | None = None) -> None:
    """Print multiple commands with descriptions."""
    if title:
        print_section_header(title)

    for command, description in commands:
        print_command(command, description)
    console.print()


def confirm_action(message: str, style: str = "yellow") -> bool:
    """Rich-styled confirmation prompt."""
    from rich.prompt import Confirm

    return Confirm.ask(f"[{style}]{message}[/{style}]")


def prompt_input(message: str, default: str | None = None) -> str | None:
    """Rich-styled input prompt."""
    from rich.prompt import Prompt

    return Prompt.ask(f"[cyan]{message}[/cyan]", default=default)


# Utility function to get the global console
def get_console() -> Console:
    """Get the global Rich console instance."""
    return console
