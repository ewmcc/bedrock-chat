"""
modules/login.py — Login module.

Provides a simple username / password login form whose credentials are
validated against the APP_USERNAME / APP_PASSWORD environment variables.

Public API
----------
login_ui(id)       → Shiny UI definition for the login panel.
login_server(id)   → Shiny server logic; returns a reactive bool
                     (True once the user has successfully authenticated).
"""

import os

from shiny import module, reactive, render, ui


# ── UI ────────────────────────────────────────────────────────────

@module.ui
def login_ui():
    return ui.div(
        ui.div(
            ui.card(
                ui.card_header(ui.h4("Sign in", class_="mb-0")),
                ui.card_body(
                    ui.input_text("username", "Username", placeholder="Username"),
                    ui.input_password("password", "Password", placeholder="Password"),
                    ui.div(
                        ui.output_text("error_msg"),
                        class_="text-danger small mb-2",
                    ),
                    ui.input_action_button(
                        "login_btn",
                        "Login",
                        class_="btn-primary w-100",
                    ),
                ),
            ),
            style="width: 360px;",
        ),
        class_="d-flex justify-content-center align-items-center",
        style="min-height: 100vh;",
    )


# ── Server ────────────────────────────────────────────────────────

@module.server
def login_server(input, output, session) -> reactive.Value:
    """
    Validates credentials and returns a reactive.Value[bool] that
    becomes True on successful login.
    """
    logged_in: reactive.Value[bool] = reactive.Value(False)
    _error: reactive.Value[str] = reactive.Value("")

    @reactive.effect
    @reactive.event(input.login_btn)
    def _handle_login():
        expected_user = os.getenv("APP_USERNAME", "")
        expected_pass = os.getenv("APP_PASSWORD", "")

        if (
            input.username() == expected_user
            and input.password() == expected_pass
            and expected_user  # reject if env var was never set
        ):
            _error.set("")
            logged_in.set(True)
        else:
            _error.set("Invalid username or password.")

    @output
    @render.text
    def error_msg():
        return _error()

    return logged_in
