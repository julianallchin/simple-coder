import os
import shlex
import sys
import atexit
from collections import namedtuple

import docker
from docker.errors import ImageNotFound, NotFound
from docker.types import Mount
from rich.console import Console

console = Console()

ExecResult = namedtuple("ExecResult", ["stdout", "stderr", "exit_code"])


class DockerManager:
    def __init__(
        self,
        image_name="simple-coder-env:latest",
        dockerfile_path="gen_env/Dockerfile",
        context_path=".",
    ):
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            console.print(
                "[red]Error:[/red] Docker is not running or misconfigured. Please start Docker and try again."
            )
            console.print(f"Details: {e}")
            sys.exit(1)

        self.image_name = image_name
        self.container = None
        self._build_image_if_needed(dockerfile_path, context_path)
        atexit.register(self.cleanup)  # Ensure container is stopped on exit

    def _build_image_if_needed(self, dockerfile_path, context_path):
        try:
            self.client.images.get(self.image_name)
            console.print(f"Docker image '{self.image_name}' found.", style="green")
        except ImageNotFound:
            console.print(
                f"Docker image '{self.image_name}' not found. Building...",
                style="yellow",
            )
            try:
                dockerfile_rel_path = os.path.relpath(dockerfile_path, context_path)
                self.client.images.build(
                    path=context_path,
                    dockerfile=dockerfile_rel_path,
                    tag=self.image_name,
                    rm=True,
                )
                console.print(
                    f"Successfully built image '{self.image_name}'.", style="green"
                )
            except Exception as e:
                console.print(f"[red]Error building Docker image:[/red] {e}")
                sys.exit(1)

    def start_container(self, host_workspace_path: str):
        if self.container:
            console.print("Container is already running.", style="yellow")
            return

        abs_workspace_path = os.path.abspath(host_workspace_path)
        os.makedirs(abs_workspace_path, exist_ok=True)

        mount = Mount(target="/workspace", source=abs_workspace_path, type="bind")

        try:
            self.container = self.client.containers.run(
                self.image_name,
                command="tail -f /dev/null",  # Keep container running
                mounts=[mount],
                working_dir="/workspace",
                detach=True,
                auto_remove=True,
            )
            console.print(
                f"Container '{self.container.short_id}' started and mounted to '{abs_workspace_path}'.",
                style="green",
            )
        except Exception as e:
            console.print(f"[red]Error starting container:[/red] {e}")
            sys.exit(1)

    def execute_command(self, command: list, workdir: str) -> ExecResult:
        if not self.container:
            return ExecResult("", "Container is not running.", 1)

        # The working directory for the shell inside the container.
        # Agent provides it relative to the workspace root.
        workdir_abs = os.path.join('/workspace', workdir)

        # Convert the command list to a single, shell-safe string.
        # e.g., ['ls', '-l', 'my file'] -> "ls -l 'my file'"
        command_str = " ".join(shlex.quote(part) for part in command)

        # Wrap the command string in a shell invocation.
        # This ensures we get authentic shell errors.
        exec_command = ["/bin/sh", "-c", command_str]

        result = self.container.exec_run(exec_command, workdir=workdir_abs, demux=True)

        stdout = result.output[0].decode("utf-8", "ignore") if result.output[0] else ""
        stderr = result.output[1].decode("utf-8", "ignore") if result.output[1] else ""

        return ExecResult(
            stdout=stdout, stderr=stderr, exit_code=result.exit_code
        )

    def stop_container(self):
        if self.container:
            try:
                self.container.stop(timeout=5)
            except NotFound:
                pass  # Already stopped or removed
            except Exception as e:
                console.print(f"[red]Error stopping container:[/red] {e}")
            finally:
                self.container = None

    def cleanup(self):
        self.stop_container()