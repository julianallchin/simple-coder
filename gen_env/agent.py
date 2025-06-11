import json
import re
from typing import Any, Dict, List

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

from .docker_manager import ExecResult

DEFAULT_SYSTEM_PROMPT_TEMPLATE = """
You are an AI coding assistant. You are running in a sandboxed environment where your workspace is /workspace.
You can interact with the file system and execute commands using the 'shell' tool. The shell is non-persistent, so changing the working directory with `cd` will not persist across commands.
Always output a thought before using the 'shell' tool. For example, "I will first check the current directory."

When using the 'shell' tool:
- The 'command' parameter must be a list of strings, representing the command and its arguments.
- The 'workdir' parameter (optional) specifies the working directory for that specific command, relative to /workspace. If not provided, it defaults to the root of your workspace.
- you are working inside a sandbox environment so feel free to install any dependencies you need.

To edit files, you MUST use a special command "apply_patch" via the 'shell' tool.
The 'command' parameter should be `["apply_patch", "YOUR_PATCH_STRING_HERE"]`.

The patch string must follow this V4A diff format:
*** Begin Patch
*** [ACTION] File: [path/to/file] -> ACTION can be one of Add, Update, or Delete.
For each snippet of code that needs to be changed, repeat the following:
[context_before]
- [old_code]
+ [new_code]
[context_after]
Context lines can be specified with '@@ function_or_class_name'.

File paths in patches should be relative to the root of the workspace.
After a tool call, you will receive a JSON output with "stdout", "stderr", and "exit_code". Use this to decide your next step.
Complete the user's request to the best of your ability.

When you are confident that you have completed the request, you MUST call the `finish` tool. This will end the session and submit your work.
The `finish` tool takes an optional `message` argument to describe your work.

"""


class GenEnvAgent:
    SHELL_TOOL_DEF = {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Runs a shell command in the /workspace directory, or applies a patch to files. Returns its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The command and its arguments. For patches, use ['apply_patch', 'PATCH_STRING']",
                    },
                    "workdir": {
                        "type": "string",
                        "description": "The working directory for the command, relative to /workspace. Defaults to the workspace root if not provided.",
                    },
                },
                "required": ["command"],
            },
        },
    }

    FINISH_TOOL_DEF = {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when you have completed the task. It will end the session and generate a patch of your changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "A summary of the changes you made and why.",
                    },
                },
                "required": [],
            },
        },
    }

    def __init__(self, model_name: str, client: OpenAI):
        self.model_name = model_name
        self.client = client
        self.console = Console()

    def initialize_conversation(self) -> List[Dict[str, Any]]:
        return [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT_TEMPLATE}]

    def get_next_action(self, conversation_history: List[Dict[str, Any]]):
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=conversation_history,
                temperature=0.7,
                tools=[self.SHELL_TOOL_DEF, self.FINISH_TOOL_DEF],
                tool_choice="auto",
            )
            return response.choices[0].message
        except Exception as e:
            self.console.print(f"[red]Error calling OpenAI API:[/red] {e}")
            raise

    def display_tool_call(self, tool_name: str, tool_args: Dict[str, Any]):
        workdir = tool_args.get("workdir", ".")

        if tool_name == "shell":
            command = tool_args.get("command", [])
            if command and command[0] == "apply_patch":
                self._format_patch(command[1])
            else:
                cmd_str = " ".join(command)
                self.console.print(
                    Panel(
                        f"$ {cmd_str}",
                        title=f"Run Command in /workspace/{workdir}",
                        border_style="blue",
                    )
                )
        elif tool_name == "finish":
            message = tool_args.get("message", "Task finished.")
            self.console.print(
                Panel(message, title="Agent called finish()", border_style="green")
            )

    def display_tool_output(self, result: ExecResult):
        output_panel = ""
        if result.stdout:
            output_panel += f"[bold green]stdout:[/bold green]\n{result.stdout.strip()}"
        if result.stderr:
            output_panel += f"\n[bold red]stderr:[/bold red]\n{result.stderr.strip()}"

        title = f"Output (exit code: {result.exit_code})"
        border_color = "green" if result.exit_code == 0 else "red"
        self.console.print(Panel(output_panel, title=title, border_style=border_color))

    def _format_patch(self, patch_text):
        file_match = re.search(r"\*\*\* (Add|Update|Delete) File: (.+)", patch_text)
        title = (
            f"Apply Patch to {file_match.group(2)}" if file_match else "Apply Patch"
        )
        content = ""
        for line in patch_text.splitlines():
            if line.startswith("+"):
                content += f"[green]{line}[/green]\n"
            elif line.startswith("-"):
                content += f"[red]{line}[/red]\n"
            else:
                content += f"{line}\n"
        self.console.print(Panel(content, title=title, border_style="magenta"))