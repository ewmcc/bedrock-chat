"""
app.py - Entry point.

Loads environment variables, wires the login and chat modules together,
and conditionally renders either the login page or the chat page
based on authentication state.
"""

from dotenv import load_dotenv

load_dotenv()  # Must happen before get_llm() so env vars are available.

from shiny import App, reactive, render, ui

from llm import get_llm
from modules.chat import chat_server, chat_ui
from modules.login import login_server, login_ui

# Initialise the LLM once at startup (cached by lru_cache in llm.py).
llm = get_llm()


# ── UI ────────────────────────────────────────────────────────────

app_ui = ui.page_fluid(
    ui.head_content(ui.tags.title("Bedrock Chat")),
    ui.output_ui("page"),
)


# ── Server ────────────────────────────────────────────────────────

def server(input, output, session):
    # Instantiate modules and capture their returned reactive values.
    logged_in: reactive.Value[bool] = login_server("login")
    chat_active: reactive.Value[bool] = chat_server("chat", llm=llm)

    # When the chat module signals logout, flip logged_in back to False.
    @reactive.effect
    def _sync_logout():
        if not chat_active():
            logged_in.set(False)

    @output
    @render.ui
    def page():
        if logged_in():
            return chat_ui("chat")
        return login_ui("login")


app = App(app_ui, server)
if __name__ == "__main__":
    app.run(launch_browser=True)
