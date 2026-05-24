"""
modules/chat.py - Chat module.

Wires Shiny's native ui.Chat component to a LangChain ChatBedrockConverse LLM.
Conversation history is kept per-session in a module-local list; full history
is sent with every request so the model has context.

Public API
----------
chat_ui(id)              → Shiny UI definition.
chat_server(id, llm)     → Shiny server logic; `llm` is a ChatBedrockConverse instance.
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from shiny import module, reactive, render, ui


_SYSTEM_PROMPT = (
    "You are a helpful, concise assistant. "
    "Answer the user's questions clearly and accurately."
)


# ── UI ────────────────────────────────────────────────────────────

@module.ui
def chat_ui():
    return ui.div(
        ui.div(
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
            style="max-width: 800px; width: 100%; padding: 1.5rem;",
        ),
        class_="d-flex justify-content-center",
        style="min-height: 100vh; padding-top: 2rem;",
    )


# ── Server ────────────────────────────────────────────────────────

@module.server
def chat_server(input, output, session, llm) -> reactive.Value:
    """
    Handles streaming chat interactions.
    Returns a reactive.Value[bool] that becomes False when the user clicks Logout.
    """
    logged_in: reactive.Value[bool] = reactive.Value(True)

    # Shiny's Chat component object - obtained from the server side.
    chat = ui.Chat(id="chat_widget", messages=[])

    @chat.on_user_submit
    async def _handle_submit():
        user_text: str = chat.user_input()

        # Build LangChain message list: system + full history + new user message.
        history = chat.messages()
        lc_messages: list[Any] = [SystemMessage(content=_SYSTEM_PROMPT)]

        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        # Stream the response back into the Chat widget.
        async def _token_generator():
            async for chunk in llm.astream(lc_messages):
                if chunk.text:
                    yield chunk.text

        await chat.append_message_stream(_token_generator())

    @reactive.effect
    @reactive.event(input.logout_btn)
    def _handle_logout():
        logged_in.set(False)

    return logged_in
