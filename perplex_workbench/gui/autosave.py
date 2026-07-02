"""Auto-save functionality for composition drafts using session state."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


def init_autosave_state():
    """Initialize auto-save session state."""
    if "autosave_enabled" not in st.session_state:
        st.session_state.autosave_enabled = False
    if "saved_drafts" not in st.session_state:
        st.session_state.saved_drafts = {}
    if "draft_recovery_dismissed" not in st.session_state:
        st.session_state.draft_recovery_dismissed = False


def save_draft(model: dict[str, Any], draft_key: str = "current_draft"):
    """Save model draft to session state.

    Args:
        model: Model to save
        draft_key: Key for this draft
    """
    if not st.session_state.get("autosave_enabled", False):
        return

    draft_data = {
        "model": model.copy(),
        "timestamp": datetime.now().isoformat(),
    }

    st.session_state.saved_drafts[draft_key] = draft_data


def load_draft(draft_key: str = "current_draft") -> dict[str, Any] | None:
    """Load model draft from session state.

    Args:
        draft_key: Key for the draft

    Returns:
        Model dictionary or None if no draft exists
    """
    draft_data = st.session_state.saved_drafts.get(draft_key)
    if draft_data:
        return draft_data.get("model")
    return None


def has_draft(draft_key: str = "current_draft") -> bool:
    """Check if a draft exists.

    Args:
        draft_key: Key for the draft

    Returns:
        True if draft exists
    """
    return draft_key in st.session_state.saved_drafts


def clear_draft(draft_key: str = "current_draft"):
    """Clear a saved draft.

    Args:
        draft_key: Key for the draft
    """
    if draft_key in st.session_state.saved_drafts:
        del st.session_state.saved_drafts[draft_key]


def get_draft_timestamp(draft_key: str = "current_draft") -> str | None:
    """Get timestamp of saved draft.

    Args:
        draft_key: Key for the draft

    Returns:
        ISO format timestamp or None
    """
    draft_data = st.session_state.saved_drafts.get(draft_key)
    if draft_data:
        return draft_data.get("timestamp")
    return None


def show_autosave_controls():
    """Render auto-save settings in sidebar."""
    init_autosave_state()

    st.sidebar.caption("💾 Auto-save")

    enable_autosave = st.sidebar.checkbox(
        "Enable auto-save",
        value=st.session_state.autosave_enabled,
        help="Save work-in-progress compositions to session state",
    )
    st.session_state.autosave_enabled = enable_autosave

    if enable_autosave:
        draft_count = len(st.session_state.saved_drafts)
        st.sidebar.caption(f"📝 {draft_count} draft(s) saved this session")

        if draft_count > 0 and st.sidebar.button("Clear all drafts", type="secondary"):
            st.session_state.saved_drafts = {}
            st.sidebar.success("All drafts cleared")


def show_draft_recovery_banner(draft_key: str = "current_draft"):
    """Show recovery banner if draft exists.

    Args:
        draft_key: Key for the draft
    """
    init_autosave_state()

    if st.session_state.get("draft_recovery_dismissed", False):
        return

    if not has_draft(draft_key):
        return

    timestamp = get_draft_timestamp(draft_key)
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%H:%M:%S")
        except (ValueError, AttributeError):
            time_str = "recently"
    else:
        time_str = "recently"

    st.info(f"🔄 Found unsaved work from {time_str}")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        if st.button("Recover", type="primary"):
            # Signal to caller that recovery was requested
            st.session_state.draft_recovery_requested = draft_key
            st.session_state.draft_recovery_dismissed = True
            st.rerun()

    with col2:
        if st.button("Dismiss"):
            st.session_state.draft_recovery_dismissed = True
            st.rerun()


def handle_draft_recovery(draft_key: str = "current_draft") -> dict[str, Any] | None:
    """Check if draft recovery was requested and return the draft.

    Args:
        draft_key: Key for the draft

    Returns:
        Recovered model or None
    """
    if st.session_state.get("draft_recovery_requested") == draft_key:
        # Clear the recovery flag
        st.session_state.draft_recovery_requested = None
        return load_draft(draft_key)
    return None


def autosave_wrapper(model: dict[str, Any], draft_key: str = "current_draft"):
    """Wrapper to auto-save model if enabled.

    Call this after any model edit.

    Args:
        model: Model to save
        draft_key: Key for this draft
    """
    if st.session_state.get("autosave_enabled", False):
        save_draft(model, draft_key)
