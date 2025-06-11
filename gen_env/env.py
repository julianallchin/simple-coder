import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from rich.console import Console

from .agent import GenEnvAgent
from .docker_manager import DockerManager, ExecResult
from .patch_utils import DiffError, process_patch
import subprocess

@dataclass
class Step:
    thought: Optional[str] = None
    tool_call: Optional[Dict] = None
    tool_output: Optional[Dict] = None
    final_patch: Optional[str] = None


class GenEnv:
    def __init__(self, model_name: str, client: OpenAI, max_steps: int = 25):
        self.max_steps = max_steps
        self.docker_manager = DockerManager()
        self.agent = GenEnvAgent(model_name, client)
        self.console = Console()
        self.project_path = None

    def _generate_git_patch(self) -> str:
        """Generates a git diff patch for the changes in the project path."""
        if not self.project_path:
            return ""
        try:
            # It is a git repo, get the diff from the initial state
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.console.print(
                "[yellow]Warning: Could not generate git diff. Was the git repository initialized correctly?[/yellow]"
            )
            return ""

    def _execute_tool_call(self, tool_args: Dict[str, Any]) -> ExecResult:
        command: Optional[List[str]] = tool_args.get("command")
        workdir_relative = tool_args.get("workdir", ".")

        if not command:
            return ExecResult("", "Shell tool error: 'command' is missing.", 1)

        if command[0] == "apply_patch":
            if len(command) > 1 and isinstance(command[1], str):
                patch_text = command[1]
                try:
                    def open_fn(p):
                        with open(os.path.join(self.project_path, p), "rt") as f:
                            return f.read()
                    def write_fn(p, c):
                        path_full = os.path.join(self.project_path, p)
                        os.makedirs(os.path.dirname(path_full), exist_ok=True)
                        with open(path_full, "wt") as f:
                            f.write(c)
                    def remove_fn(p):
                        os.unlink(os.path.join(self.project_path, p))

                    if not patch_text.strip().startswith("*** Begin Patch"):
                        patch_text = "*** Begin Patch\n" + patch_text
                    if not patch_text.strip().endswith("*** End Patch"):
                        patch_text = patch_text + "\n*** End Patch"

                    result = process_patch(patch_text, open_fn, write_fn, remove_fn)
                    return ExecResult(stdout=result, stderr="", exit_code=0)
                except (DiffError, FileNotFoundError) as e:
                    return ExecResult(stdout="", stderr=str(e), exit_code=1)
            else:
                return ExecResult("", "'apply_patch' requires a patch string.", 1)
        else:
            return self.docker_manager.execute_command(command, workdir_relative)

    def run_episode(
        self, project_path: str, prompt: str
    ) -> Tuple[List[Step], Optional[str]]:
        self.project_path = os.path.abspath(project_path)
        # --- Initialize Git repo to track changes from the start ---
        try:
            # 1. Initialize the repository FIRST
            subprocess.run(["git", "init"], cwd=self.project_path, check=True, capture_output=True)

            # 2. Now, set the local config for the newly created repo
            git_config_user = ["git", "config", "user.name", "Agent"]
            git_config_email = ["git", "config", "user.email", "agent@example.com"]
            subprocess.run(git_config_user, cwd=self.project_path, check=True, capture_output=True)
            subprocess.run(git_config_email, cwd=self.project_path, check=True, capture_output=True)

            # 3. Add all files and make an initial commit to serve as a baseline
            subprocess.run(["git", "add", "."], cwd=self.project_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit", "--no-verify"], cwd=self.project_path, check=True, capture_output=True)
            self.console.print("[green]Initialized git repository to track changes.[/green]")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(e)
            self.console.print("[yellow]Warning: Failed to initialize git repository. Final patch generation via `finish` tool will be unavailable.[/yellow]")

        self.docker_manager.start_container(self.project_path)

        conversation_history = self.agent.initialize_conversation()
        conversation_history.append({"role": "user", "content": prompt})

        steps: List[Step] = []
        final_patch = None

        try:
            for turn in range(self.max_steps):
                self.console.print(
                    f"\n[bold yellow]--- Turn {turn + 1}/{self.max_steps} ---[/bold yellow]"
                )

                response_message = self.agent.get_next_action(conversation_history)
                conversation_history.append(response_message)

                step = Step(thought=response_message.content)

                self.console.print(f"\n[cyan]Assistant:[/cyan] {response_message.content}")

                if response_message.tool_calls:
                    tool_call = response_message.tool_calls[0]
                    step.tool_call = tool_call.function.to_dict()
                    tool_name = tool_call.function.name

                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                        self.agent.display_tool_call(tool_name, tool_args)

                        if tool_name == "shell":
                            exec_result = self._execute_tool_call(tool_args)

                            tool_output_json = json.dumps(exec_result._asdict())
                            step.tool_output = exec_result._asdict()
                            self.agent.display_tool_output(exec_result)

                            conversation_history.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": "shell",
                                    "content": tool_output_json,
                                }
                            )
                        elif tool_name == "finish":
                            final_patch = self._generate_git_patch()
                            step.final_patch = final_patch
                            steps.append(step)
                            return steps, final_patch  # Explicitly end execution

                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON for tool arguments: {e}"
                        conversation_history.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": json.dumps({"error": error_msg}),
                            }
                        )
                        self.console.print(f"[red]Error:[/red] {error_msg}")
                        step.tool_output = {"error": error_msg}
       
                steps.append(step)
        finally:
            self.docker_manager.stop_container()

        # If loop finishes without `finish` being called (e.g., max_turns),
        # generate a patch as a fallback.
        if final_patch is None:
            final_patch = self._generate_git_patch()
            self.console.print("[yellow]Agent did not call `finish()`. Generating final patch from current state.[/yellow]")
        
        self.project_path = None

        return steps, final_patch