#!/usr/bin/env python3

import json
import os
import shlex
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import Config
from ..ui.theme import PanelTheme

from rich.tree import Tree

try:  
    from InquirerPy import inquirer
except Exception:
    inquirer = None

from .base import BasePersona, PersonaResult


@dataclass
class PlanStep:
    description: str
    command: str
    confirm: bool = True
    interactive: bool = False

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "command": self.command,
            "confirm": self.confirm,
            "interactive": self.interactive,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PlanStep":
        return cls(
            description=str(data.get("description", "")),
            command=str(data.get("command", "")),
            confirm=bool(data.get("confirm", True)),
            interactive=bool(data.get("interactive", False)),
        )


READ_ONLY_COMMANDS = {
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "sed",
    "awk",
    "grep",
    "rg",
    "find",
    "stat",
    "wc",
    "tree",
    "bat",
    "batcat",
}


class HelpAssistentPersona(BasePersona):
    name = "help_assistent"
    MAX_STEPS_PER_RUN = 6
    COMMAND_HISTORY_LIMIT = 20

    def process(self, user_message: str, context: Dict) -> PersonaResult:
        prev_state = (context.get("metadata") or {}).get(self.name, {})
        pending_plan = self._hydrate_pending_plan(prev_state.get("pending_plan"))
        executed_commands: List[str] = list(prev_state.get("executed_commands", []))[-self.COMMAND_HISTORY_LIMIT :]

        executed_steps: List[PlanStep] = []
        executions: List[Dict] = []
        context_state = dict(context)
        avoid_interactive = False
        max_iterations = 10
        executor = getattr(self.ai_manager, "command_executor", None)
        status = None

        if executor and hasattr(executor, "console"):
            status = executor.console.status("[cyan]Thinking…[/cyan]", spinner="dots")
            status.start()

        try:
            plan_queue: List[PlanStep] = pending_plan

            for iteration in range(max_iterations):
                if len(executed_steps) >= self.MAX_STEPS_PER_RUN:
                    break

                if not plan_queue:
                    plan_steps = self._create_plan(
                        user_message,
                        context_state,
                        executions,
                        avoid_interactive,
                    )

                    if not plan_steps:
                        if executions:
                            break

                        fallback_steps = self._default_plan()
                        plan_queue.extend(fallback_steps)
                        if not plan_queue:
                            break
                    else:
                        plan_queue.extend(plan_steps)

                if not plan_queue:
                    break

                step = plan_queue.pop(0)
                if step.interactive:
                    avoid_interactive = True

                repeated_command = step.command.strip() in executed_commands
                if repeated_command:
                    executions.append(
                        {
                            "step": len(executed_steps) + 1,
                            "description": step.description,
                            "command": step.command,
                            "status": "skipped",
                            "exit_code": None,
                            "stdout": "",
                            "stderr": "Rejected repeated command",
                            "interactive": step.interactive,
                            "summary": "Skipped repeated command to avoid redundant loop.",
                        }
                    )
                    break

                record = self._execute_single_step(len(executed_steps) + 1, step)
                executed_steps.append(step)
                executions.append(record)
                executed_commands.append(step.command.strip())
                executed_commands = executed_commands[-self.COMMAND_HISTORY_LIMIT :]

                context_state["shell_context"] = self.ai_manager.context_manager.build_context_for_ai()

                if record.get("status") in {"skipped", "invalid"}:
                    break

            if not executed_steps and not executions:
                executed_steps = self._default_plan()
                executions = [
                    self._execute_single_step(index + 1, step)
                    for index, step in enumerate(executed_steps)
                ]
        finally:
            if status is not None:
                status.stop()

        tree = self._build_plan_tree(executed_steps, executions)

        remaining_plan = [step.to_dict() for step in plan_queue]
        execution_summary = self._build_execution_summary(executions)

        persona_metadata = {
            "type": "planner",
            "plan": [step.__dict__ for step in executed_steps],
            "executions": executions,
            "pending_plan": remaining_plan,
            "executed_commands": executed_commands,
            "last_summary": execution_summary,
        }

        final_messages = self._build_final_messages(
            user_message,
            context_state,
            executed_steps,
            executions,
        )

        return PersonaResult(
            messages=final_messages,
            metadata=persona_metadata,
            renderable=tree,
        )

    def _default_plan(self) -> List[PlanStep]:
        return [
            PlanStep(description="Show current directory", command="pwd", confirm=True),
            PlanStep(description="List Python files in this directory", command='ls "*.py"', confirm=True),
        ]

    def _create_plan(
        self,
        user_message: str,
        context: Dict,
        executions: List[Dict],
        avoid_interactive: bool,
    ) -> List[PlanStep]:
        sanitized_plan: List[PlanStep] = []
        enforce_non_interactive = avoid_interactive

        for _ in range(2):
            messages = self._build_plan_messages(
                user_message,
                context,
                enforce_non_interactive,
                executions,
            )

            try:
                plan_text = self.ai_manager.complete(messages, max_tokens=600)
                plan_data = json.loads(plan_text)
            except Exception:
                continue

            plan_steps = self._parse_plan_steps(plan_data)

            if not plan_steps:
                continue

            if enforce_non_interactive or not self._contains_interactive_commands(plan_steps):
                sanitized_plan = plan_steps
                break

            enforce_non_interactive = True
            sanitized_plan = plan_steps

        return sanitized_plan[:3] if sanitized_plan else []

    def _build_plan_messages(
        self,
        user_message: str,
        context: Dict,
        avoid_interactive: bool,
        executions: List[Dict],
    ) -> List[dict]:
        shell_context = context.get("shell_context") or ""

        interactive_list = ", ".join(sorted(Config.INTERACTIVE_COMMANDS))
        extra_instruction = (
            " Avoid the following interactive commands: "
            f"{interactive_list}. Use non-interactive alternatives such as cat <<'EOF' > file."
        ) if avoid_interactive else ""

        instructions = (
            "You are a shell planner persona inside a hybrid IDE. "
            "Propose the next shell command step based on the latest context. "
            "Respond ONLY with valid JSON: {\"steps\": [{\"description\": str, \"command\": str, \"confirm\": bool}]}. "
            "Return an empty steps array when no further actions are required. "
            "Limit each response to at most one step so the planner can re-evaluate after execution. "
            "Do NOT repeat a command if it was already executed with the same output unless explicit re-run is needed. "
            "Use double quotes for wildcards when needed (e.g. \"ls *.py\"). "
            "Do NOT use destructive commands (rm, sudo, etc.). "
            "Do NOT use directory-changing commands like 'cd'. "
            "Always address files using paths relative to the current working directory. "
            "When inspecting a file, show an excerpt (e.g. head -n 10 or sed -n '1,10p') instead of only listing it. "
            "Only create new files (touch) if the user explicitly requests it."
        ) + extra_instruction

        history_text = self._format_execution_history(executions)

        user_prompt = [
            f"Current working directory: {os.getcwd()}",
            f"Recent shell context (if any):\n{shell_context}",
            f"User request: {user_message}",
            "Provide the next shell step (or [] if done).",
        ]

        if history_text:
            user_prompt.append("Recent step summaries:")
            user_prompt.append(history_text)

        return [
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": "\n\n".join(user_prompt),
            },
        ]

    def _format_execution_history(self, executions: List[Dict]) -> str:
        if not executions:
            return ""

        lines: List[str] = []
        for record in executions[-3:]:
            step_no = record.get("step")
            description = record.get("description", "")
            status = record.get("status", "unknown")
            exit_code = record.get("exit_code")
            summary = record.get("summary") or "(no output captured)"
            lines.append(
                "\n".join(
                    filter(
                        None,
                        [
                            f"Step {step_no}: {description}",
                            f"Status: {status} (exit={exit_code})",
                            summary,
                        ],
                    )
                )
            )

        return "\n\n".join(lines)

    def _build_execution_summary(self, executions: List[Dict]) -> str:
        if not executions:
            return ""

        lines: List[str] = []
        for record in executions[-5:]:
            desc = record.get("description", "")
            cmd = record.get("command", "")
            status = record.get("status")
            exit_code = record.get("exit_code")
            summary = record.get("summary") or ""
            lines.append(
                " | ".join(
                    filter(
                        None,
                        [
                            desc,
                            f"cmd: {cmd}",
                            f"status: {status} (exit={exit_code})",
                            summary,
                        ],
                    )
                )
            )

        return "\n".join(lines)

    def _parse_plan_steps(self, plan_data: Dict) -> List[PlanStep]:
        steps_data = plan_data.get("steps") if isinstance(plan_data, dict) else []
        plan_steps: List[PlanStep] = []

        for item in steps_data or []:
            description = str(item.get("description", "")).strip()
            command = str(item.get("command", "")).strip()
            confirm = bool(item.get("confirm", True))

            if not description or not command:
                continue

            plan_steps.append(
                PlanStep(
                    description=description,
                    command=command,
                    confirm=confirm,
                    interactive=self._is_interactive_command(command),
                )
            )

        return plan_steps

    def _contains_interactive_commands(self, plan_steps: List[PlanStep]) -> bool:
        return any(step.interactive for step in plan_steps)

    def _is_interactive_command(self, command: str) -> bool:
        if not command:
            return False

        base = command.strip().split()[0].lower()
        if base in Config.INTERACTIVE_COMMANDS:
            return True

        return False

    def _confirm_step(self, index: int, step: PlanStep) -> bool:
        default_choice = "execute" if step.confirm else "skip"

        if inquirer is None:
            return default_choice == "execute"

        message = (
            f"Step {index}: {step.description}\n"
            f"Command: {step.command}\n"
            "Execute this step?"
        )

        if step.interactive:
            message += (
                "\n[WARNING] This command is interactive and may require manual control."
                " Only continue if that is intended."
            )
            default_choice = "skip"

        try:
            response = inquirer.select(
                message=message,
                choices=[
                    {"name": " Run this step", "value": "execute"},
                    {"name": " Skip this step", "value": "skip"},
                ],
                default=default_choice,
                border=True,
            ).execute()
            return response == "execute"
        except Exception:
            return default_choice == "execute"

    def _execute_single_step(self, index: int, step: PlanStep) -> Dict:
        command = step.command.strip()

        if not command:
            record = {
                "status": "invalid",
                "step": index,
                "description": step.description,
                "command": step.command,
                "exit_code": None,
                "stdout": "",
                "stderr": "Command missing",
                "interactive": step.interactive,
                "summary": "Command missing.",
            }
            self._display_step_feedback(step, record)
            return record

        auto_execute = (not step.interactive) and self._is_read_only_command(command)

        if auto_execute:
            should_execute = True
        else:
            should_execute = self._confirm_step(index, step)

        if not should_execute:
            record = {
                "status": "skipped",
                "step": index,
                "description": step.description,
                "command": step.command,
                "exit_code": None,
                "stdout": "",
                "stderr": "User skipped",
                "interactive": step.interactive,
                "summary": "Step skipped by user.",
            }
            self._display_step_feedback(step, record)
            return record

        try:
            result = self.ai_manager.run_shell_command(step.command)
        except Exception as error: 
            result = {
                "command": step.command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {error}",
            }

        record = self._format_execution_record(index, step, result)
        if auto_execute:
            record["auto_executed"] = True
        record["summary"] = self._summarize_execution(record)
        self._display_step_feedback(step, record)
        return record

    def _build_final_messages(
        self,
        user_message: str,
        context: Dict,
        plan: List[PlanStep],
        executions: List[Dict],
    ) -> List[dict]:
        supplemental = context.get("supplemental_text", "")

        system_msg = (
            "You are persona help_assistent. Combine the observed command outputs to answer the question. "
            "Mirror the user's language when possible and explain insights from the inspected files or commands."
        )

        if supplemental:
            system_msg += f"\nSupplemental information:\n{supplemental}"

        plan_lines = []
        for exec_info in executions:
            status = exec_info.get("status", "")
            exit_code = exec_info.get("exit_code")
            stdout = self._truncate(exec_info.get("stdout", ""))
            stderr = self._truncate(exec_info.get("stderr", ""))
            plan_lines.append(
                "\n".join(
                    filter(
                        None,
                        [
                            f"Step {exec_info.get('step')}: {exec_info.get('description')}",
                            f"Command: {exec_info.get('command')}",
                            f"Status: {status} (exit={exit_code})",
                            f"Stdout: {stdout}" if stdout else None,
                            f"Stderr: {stderr}" if stderr else None,
                        ],
                    )
                )
            )

        plan_summary = "\n---\n".join(plan_lines) if plan_lines else "(no steps executed)"

        if persona_metadata := (context.get("metadata") or {}).get(self.name):
            previous_summary = persona_metadata.get("last_summary")
            if previous_summary and previous_summary not in plan_summary:
                plan_summary = previous_summary + "\n---\n" + plan_summary

        user_content = (
            f"Original request: {user_message}\n"
            f"Planner steps summary:\n{plan_summary}\n\n"
            "Provide a final response summarizing the observations and offering next actions when appropriate."
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]

    def _truncate(self, text: Optional[str], limit: int = 700) -> str:
        if not text:
            return ""
        cleaned = text.strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3] + "..."

    def _execute_plan_steps(self, plan_steps: List[PlanStep]) -> List[Dict]:
        executions: List[Dict] = []

        if not plan_steps:
            return executions

        for index, step in enumerate(plan_steps, start=1):
            record = self._execute_single_step(index, step)
            executions.append(record)

        return executions

    def _format_execution_record(self, index: int, step: PlanStep, result: Dict) -> Dict:
        exit_code = result.get("exit_code", 0)
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""

        return {
            "step": index,
            "description": step.description,
            "command": step.command,
            "status": "executed",
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "interactive": step.interactive,
        }

    def _summarize_execution(self, record: Dict) -> str:
        stdout = record.get("stdout", "") or ""
        stderr = record.get("stderr", "") or ""
        parts: List[str] = []

        if record.get("auto_executed"):
            parts.append("auto-executed (read-only)")

        if stdout.strip():
            parts.append(f"stdout: {self._truncate(stdout, 200)}")

        if stderr.strip():
            parts.append(f"stderr: {self._truncate(stderr, 200)}")

        if not parts:
            exit_code = record.get("exit_code")
            parts.append(f"no output (exit={exit_code})")

        return " | ".join(parts)

    def _is_read_only_command(self, command: str) -> bool:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return False

        if not tokens:
            return False

        base = os.path.basename(tokens[0])

        if base in READ_ONLY_COMMANDS:
            if base == "sed" and any(flag in tokens for flag in {"-i", "--in-place"}):
                return False
            return True

        return False

    def _hydrate_pending_plan(self, plan_data: Optional[List[Dict]]) -> List[PlanStep]:
        pending: List[PlanStep] = []
        if not plan_data:
            return pending

        for item in plan_data:
            try:
                step = PlanStep.from_dict(item)
            except Exception:
                continue
            if not step.command.strip():
                continue
            if not step.interactive:
                step.interactive = self._is_interactive_command(step.command)
            pending.append(step)
        return pending

    def _build_plan_tree(self, plan_steps: List[PlanStep], executions: List[Dict]) -> Tree:
        tree = Tree("[bold blue]Planner (Help Assistent Persona)[/bold blue]")

        execution_lookup = {exec_info.get("step"): exec_info for exec_info in executions if exec_info}

        for index, step in enumerate(plan_steps, start=1):
            exec_info = execution_lookup.get(index, {})
            status = exec_info.get("status", "skipped")
            exit_code = exec_info.get("exit_code")
            stdout = exec_info.get("stdout", "")
            stderr = exec_info.get("stderr", "")

            if status == "executed":
                if exit_code == 0 and not stderr:
                    status_label = "[green]Executed[/green]"
                elif exit_code == 0:
                    status_label = "[yellow]Executed with warnings[/yellow]"
                else:
                    status_label = "[red]Failed[/red]"
                preview_source = (stdout or "") + (stderr or "")
                output_preview = self._truncate(preview_source or f"Exit code {exit_code}")
                reason = f"Exit code {exit_code}"
            elif status == "invalid":
                status_label = "[red]Invalid command[/red]"
                output_preview = ""
                reason = "Empty command"
            else:
                status_label = "[yellow]Skipped[/yellow]"
                output_preview = ""
                reason = exec_info.get("stderr", "User skipped")

            if step.interactive:
                reason = (reason + " | interactive command") if reason else "interactive command"

            node = tree.add(f"Step {index}: {step.description} -> {status_label}")
            node.add(f"[cyan]Command:[/] {step.command}")
            if output_preview:
                node.add(f"[dim]{output_preview}[/dim]")
            else:
                node.add(f"[dim]{reason}[/dim]")

        return tree

    def _display_step_feedback(self, step: PlanStep, record: Dict) -> None:
        executor = getattr(self.ai_manager, "command_executor", None)
        if not executor or not hasattr(executor, "console"):
            return

        console = executor.console

        status = record.get("status", "unknown")
        exit_code = record.get("exit_code")
        stdout = record.get("stdout", "") or ""
        stderr = record.get("stderr", "") or ""

        if status == "executed":
            if exit_code == 0 and not stderr:
                panel_style = "success"
                status_label = "Executed"
            elif exit_code == 0:
                panel_style = "warning"
                status_label = "Executed (warnings)"
            else:
                panel_style = "error"
                status_label = "Failed"

            body_lines = [
                f"[dim]Command:[/dim] {step.command}",
                f"Status: {status_label} (exit={exit_code})",
            ]
            if stdout.strip():
                body_lines.append(f"Stdout:\n{self._truncate(stdout)}")
            if stderr.strip():
                body_lines.append(f"Stderr:\n{self._truncate(stderr)}")
        elif status == "skipped":
            panel_style = "warning"
            body_lines = [
                f"[dim]Command:[/dim] {step.command}",
                "Status: Skipped",
                f"Reason: {stderr or 'User skipped'}",
            ]
        else:
            panel_style = "error"
            body_lines = [
                f"[dim]Command:[/dim] {step.command}",
                "Status: Invalid",
                f"Reason: {stderr or 'Invalid command'}",
            ]

        if step.interactive:
            body_lines.append("[dim]Note: interactive command[/dim]")

        panel_content = "\n".join(body_lines)
        console.print(
            PanelTheme.build(
                panel_content,
                title=f"Step {record.get('step', '?')}: {step.description}",
                style=panel_style,
                fit=True,
            )
        )
