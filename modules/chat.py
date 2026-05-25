"""
modules/chat.py - Chat module.

Wires Shiny's native ui.Chat component to a LangChain ChatBedrockConverse LLM.
Conversation history is kept per-session; full history is sent with every
request so the model has context.

Features
--------
- Sidebar with configurable system prompt, temperature, and max tokens.
- Tool toggles for DuckDuckGo web search and Wikipedia lookup.
- Running token counter (input / output / total) updated after each turn.

Public API
----------
chat_ui(id)          → Shiny UI definition.
chat_server(id)      → Shiny server logic; creates its own LLM per session.
                       Returns reactive.Value[bool] (False on logout).
"""

import json
from typing import Any

from ddgs import DDGS
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from shiny import module, reactive, render, ui
import wikipedia

from llm import get_llm



_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, concise assistant. "
    "Answer the user's questions clearly and accurately."
)
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_TOKENS = 1024


# ── Tool Definitions ──────────────────────────────────────────────

@tool
def tool_search(query: str) -> str:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query string.
        
    Returns:
        A string with search results.
    """
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)
        if not results:
            return "No search results found."
        
        formatted_results = []
        for result in results:
            formatted_results.append(
                f"Title: {result.get('title', '')}\n"
                f"Body: {result.get('body', '')}\n"
                f"Link: {result.get('href', '')}"
            )
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def tool_wiki(query: str) -> str:
    """
    Search Wikipedia for information.
    
    Args:
        query: The search query string.
        
    Returns:
        A string with Wikipedia summary or relevant information.
    """
    try:
        results = wikipedia.search(query, results=3)
        if not results:
            return "No Wikipedia results found."
        
        formatted_results = []
        for title in results:
            try:
                page = wikipedia.page(title, auto_suggest=False)
                formatted_results.append(
                    f"Title: {page.title}\n"
                    f"Summary: {page.summary[:500]}...\n"
                    f"URL: {page.url}"
                )
            except wikipedia.exceptions.DisambiguationError as e:
                formatted_results.append(f"Disambiguation for '{title}': {str(e)[:200]}")
            except wikipedia.exceptions.PageError:
                continue
        
        return "\n\n".join(formatted_results) if formatted_results else "No detailed results found."
    except Exception as e:
        return f"Wikipedia search error: {str(e)}"


# Pre-build tool instances (stateless, safe to share across sessions).
_ALL_TOOLS = {
    "tool_search": tool_search,
    "tool_wiki": tool_wiki,
}


# ── UI ────────────────────────────────────────────────────────────

@module.ui
def chat_ui():
    sidebar = ui.sidebar(
        ui.h6("Model Parameters", class_="text-muted text-uppercase mb-2"),
        ui.input_text_area(
            "system_prompt",
            "System Prompt",
            value=_DEFAULT_SYSTEM_PROMPT,
            rows=4,
            resize="vertical",
        ),
        ui.input_slider(
            "temperature",
            "Temperature",
            min=0.0,
            max=1.0,
            value=_DEFAULT_TEMPERATURE,
            step=0.1,
        ),
        ui.input_numeric(
            "max_tokens",
            "Max Output Tokens",
            value=_DEFAULT_MAX_TOKENS,
            min=256,
            max=8192,
            step=256,
        ),
        ui.input_action_button(
            "apply_btn",
            "Apply",
            class_="btn btn-sm btn-primary w-100 mt-1",
        ),
        ui.hr(),
        ui.h6("Tools", class_="text-muted text-uppercase mb-2"),
        ui.input_checkbox("tool_search", "Web Search (DuckDuckGo)", value=False),
        ui.input_checkbox("tool_wiki", "Wikipedia", value=False),
        ui.hr(),
        ui.h6("Tokens", class_="text-muted text-uppercase mb-2"),
        ui.output_ui("token_display"),
        ui.hr(),
        ui.h6("Context", class_="text-muted text-uppercase mb-2"),
        ui.input_slider(
            "context_window",
            "Context Window (turns)",
            min=1,
            max=20,
            value=10,
            step=1,
        ),
        width=280,
        open="open",
    )

    main = ui.div(
        ui.div(
            ui.h5("Bedrock Chat", class_="mb-0"),
            ui.input_action_button(
                "logout_btn",
                "Logout",
                class_="btn btn-sm btn-outline-secondary",
            ),
            class_="d-flex justify-content-between align-items-center mb-3",
        ),
        ui.chat_ui("chat_widget"),
    )

    return ui.page_sidebar(
        sidebar,
        main,
        fillable=True,
    )


# ── Server ────────────────────────────────────────────────────────

@module.server
def chat_server(input, output, session) -> reactive.Value:
    """
    Handles streaming chat interactions.
    Creates its own LLM per session, rebuilds it when Apply is clicked.
    Returns a reactive.Value[bool] that becomes False when the user clicks Logout.
    """
    logged_in: reactive.Value[bool] = reactive.Value(True)

    # Per-session LLM instance (rebuilt on Apply).
    _llm: reactive.Value[Any] = reactive.Value(
        get_llm(temperature=_DEFAULT_TEMPERATURE, max_tokens=_DEFAULT_MAX_TOKENS)
    )

    # Cumulative token counters.
    _in_tokens: reactive.Value[int] = reactive.Value(0)
    _out_tokens: reactive.Value[int] = reactive.Value(0)

    # Shiny Chat component.
    chat = ui.Chat(id="chat_widget", messages=[])

    # ── Apply button: rebuild LLM with new params ──────────────────
    @reactive.effect
    @reactive.event(input.apply_btn)
    def _apply_params():
        _llm.set(
            get_llm(
                temperature=float(input.temperature()),
                max_tokens=int(input.max_tokens()),
            )
        )

    # ── Chat submit handler ────────────────────────────────────────
    @chat.on_user_submit
    async def _handle_submit():
        llm = _llm()
        system_prompt: str = input.system_prompt() or _DEFAULT_SYSTEM_PROMPT

        # Build LangChain message list: system + trimmed history.
        n = input.context_window()
        history = chat.messages()[-(n * 2):]
        lc_messages: list[Any] = [SystemMessage(content=system_prompt)]
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        # Collect enabled tools.
        active_tools = [
            tool
            for key, tool in _ALL_TOOLS.items()
            if getattr(input, key, lambda: False)()
        ]

        if not active_tools:
            # ── Plain streaming (no tools) ─────────────────────────
            in_used = 0
            out_used = 0

            async def _stream():
                nonlocal in_used, out_used
                async for chunk in llm.astream(lc_messages):
                    if chunk.usage_metadata:
                        in_used = chunk.usage_metadata.get("input_tokens", 0)
                        out_used = chunk.usage_metadata.get("output_tokens", 0)
                    if chunk.text:
                        yield chunk.text

            await chat.append_message_stream(_stream())
            _in_tokens.set(_in_tokens() + in_used)
            _out_tokens.set(_out_tokens() + out_used)

        else:
            # ── Agentic loop (tools enabled) ───────────────────────
            bound_llm = llm.bind_tools(active_tools)
            tool_map = {t.name: t for t in active_tools}
            loop_messages = list(lc_messages)
            in_used = 0
            out_used = 0

            while True:
                response = await bound_llm.ainvoke(loop_messages)

                # Accumulate tokens.
                if response.usage_metadata:
                    in_used += response.usage_metadata.get("input_tokens", 0)
                    out_used += response.usage_metadata.get("output_tokens", 0)

                # Stream any intermediate text the model produced alongside
                # tool calls (interpretation / chain-of-thought narration).
                intermediate_text = ""
                if isinstance(response.content, list):
                    for block in response.content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            intermediate_text += block.get("text", "")
                elif isinstance(response.content, str):
                    intermediate_text = response.content

                if not response.tool_calls:
                    # No more tool calls — stream the final text response.
                    if intermediate_text:
                        await chat.append_message_stream(
                            _single_stream(intermediate_text)
                        )
                    break

                # Stream intermediate interpretation before tool calls, if any.
                if intermediate_text.strip():
                    await chat.append_message_stream(
                        _single_stream(
                            f"💬 **Interpretation**\n\n{intermediate_text}\n\n"
                        )
                    )

                # Execute each requested tool and stream request + result.
                loop_messages.append(response)
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc["args"]

                    try:
                        args_json = json.dumps(tool_args, indent=2)
                    except Exception:
                        args_json = str(tool_args)

                    # ── Stream tool call request ───────────────────
                    await chat.append_message_stream(
                        _single_stream(
                            f"🔧 **Tool call**: `{tool_name}`\n"
                            f"```json\n{args_json}\n```\n\n"
                        )
                    )

                    # ── Execute tool ───────────────────────────────
                    tool_result = ""
                    if tool_name in tool_map:
                        try:
                            tool_result = tool_map[tool_name].invoke(tool_args)
                        except Exception as exc:
                            tool_result = f"Tool error: {exc}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"

                    # ── Stream tool result ─────────────────────────
                    await chat.append_message_stream(
                        _single_stream(_tool_result_block(tool_name, tool_result))
                    )

                    loop_messages.append(
                        ToolMessage(content=str(tool_result), tool_call_id=tc["id"])
                    )

            _in_tokens.set(_in_tokens() + in_used)
            _out_tokens.set(_out_tokens() + out_used)

    # ── Token display ──────────────────────────────────────────────

    @output
    @render.ui
    def token_display():
        i = _in_tokens()
        o = _out_tokens()
        t = i + o
        return ui.div(
            ui.div(
                ui.span("Input", class_="text-muted small"),
                ui.span(f"{i:,}", class_="fw-semibold"),
                class_="d-flex justify-content-between",
            ),
            ui.div(
                ui.span("Output", class_="text-muted small"),
                ui.span(f"{o:,}", class_="fw-semibold"),
                class_="d-flex justify-content-between",
            ),
            ui.hr(class_="my-1"),
            ui.div(
                ui.span("Total", class_="text-muted small"),
                ui.span(f"{t:,}", class_="fw-semibold"),
                class_="d-flex justify-content-between",
            ),
        )

    # ── Logout ─────────────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.logout_btn)
    def _handle_logout():
        logged_in.set(False)

    return logged_in


# ── Helpers ───────────────────────────────────────────────────────

async def _single_stream(text: str):
    """Yield a pre-formed string as a one-shot async generator for append_message_stream."""
    yield text


def _tool_result_block(tool_name: str, result: str) -> str:
    """Format a tool result with auto-expanding height and scrollable container."""
    return (
        f"📥 **Result**: `{tool_name}`\n"
        f"<pre style='white-space:pre-wrap;word-break:break-word;"
        f"max-height:400px;overflow-y:auto;padding:8px;"
        f"background:#f6f8fa;border-radius:4px;font-size:0.85em;margin:8px 0'>"
        f"{result}"
        f"</pre>\n\n"
    )
