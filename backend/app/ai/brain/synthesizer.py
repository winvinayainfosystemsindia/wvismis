"""
AI Engine — Response Synthesizer
===============================

Transforms raw tool results and LLM reasoning into professional, human-readable summaries.
"""

from app.ai.brain.schemas import ToolCallRequest, ToolResult


class Synthesizer:
    """Orchestrates the creation of the final user response from tool results."""

    def synthesize_tool_results(
        self,
        results: list[tuple[ToolCallRequest, ToolResult]],
        planned_response: str | None = None,
    ) -> str:
        """Builds a professional response from a list of tool execution outcomes."""
        if not results:
            return planned_response or "I have processed your request."

        response_lines = []
        for req, res in results:
            if res.success:
                response_lines.append(res.message)
            else:
                response_lines.append(f"Tool '{req.tool_name}' encountered an issue: {res.message}")

        full_content = "\n\n".join(response_lines)
        return full_content or planned_response or "Task completed."
