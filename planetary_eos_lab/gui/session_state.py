"""Session state management for Streamlit GUI."""
from __future__ import annotations

from typing import Any, Optional

import streamlit as st


def init_session_state() -> None:
    """Initialize all session state variables with defaults."""
    defaults = {
        "workspace_mode": "Run Pipeline",
        "workflow_step_index": 0,
        "workflow_step_choice": "1. Setup & Select Model",
        "selected_project": None,
        "last_run_project": None,
        "last_export_dir": None,
        "show_advanced_options": False,
        "auto_advance_steps": True,
        "notifications": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_state(key: str, default: Any = None) -> Any:
    """Get a value from session state with optional default.

    Args:
        key: Session state key
        default: Default value if key doesn't exist

    Returns:
        Value from session state or default
    """
    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in session state.

    Args:
        key: Session state key
        value: Value to set
    """
    st.session_state[key] = value


def add_notification(message: str, level: str = "info") -> None:
    """Add a notification to the session state.

    Args:
        message: Notification message
        level: Notification level ("info", "success", "warning", "error")
    """
    if "notifications" not in st.session_state:
        st.session_state["notifications"] = []

    st.session_state["notifications"].append({"message": message, "level": level})


def get_notifications() -> list[dict[str, str]]:
    """Get all pending notifications.

    Returns:
        List of notification dictionaries
    """
    return st.session_state.get("notifications", [])


def clear_notifications() -> None:
    """Clear all notifications from session state."""
    st.session_state["notifications"] = []


def display_notifications() -> None:
    """Display and clear all pending notifications."""
    notifications = get_notifications()

    for notification in notifications:
        message = notification["message"]
        level = notification["level"]

        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)

    clear_notifications()


def persist_form_state(prefix: str, values: dict[str, Any]) -> None:
    """Persist form values to session state.

    Args:
        prefix: Prefix for state keys
        values: Dictionary of form values to persist
    """
    for key, value in values.items():
        set_state(f"{prefix}_{key}", value)


def restore_form_state(prefix: str, keys: list[str]) -> dict[str, Any]:
    """Restore form values from session state.

    Args:
        prefix: Prefix for state keys
        keys: List of keys to restore

    Returns:
        Dictionary of restored values
    """
    return {key: get_state(f"{prefix}_{key}") for key in keys}
