# Requirements: Coverage Coach corner dock

Note: written after the code. The dock was built in a Kiro CLI vibe session on 2026-10-24 and this spec records
what was built and how it was verified. It did not drive the work.

## Introduction

The Coverage Coach used to open as a full-height panel on the right that pushed the dashboard aside. Members
should be able to chat while still reading their status, so the coach becomes a messaging-style dock: a slim bar in
the bottom-right corner that expands into a chat box in the same corner.

Scope: `app/coach_widget.py` (shell) and `app/agent_panel.py` (chat body) only. The coach's decisions
(`src/proofkit/integration/coach.py`) do not change, and the coach stays read-only.

## Requirement 1: Docked in the corner

**User story:** As a member, I want the coach out of the way until I need it, so it never hides my status.

1. WHILE the coach is closed, THE widget SHALL show one bar fixed to the bottom-right edge, labelled "Coverage Coach".
2. WHEN the member activates the bar, THE widget SHALL open a chat box anchored to the same bottom-right corner.
3. WHILE the chat box is open, THE page SHALL keep its full width; nothing SHALL reflow or shift the dashboard.
4. WHILE the chat box is open, THE dashboard SHALL stay scrollable and clickable outside the box.

## Requirement 2: Header controls

1. THE chat box header SHALL show the title, a live-AI indicator (on or offline), a settings control, minimize and close.
2. WHEN the member minimizes (button or Escape), THE widget SHALL return to the bar and SHALL keep the conversation.
3. WHEN the member closes, THE widget SHALL return to the bar and SHALL clear the conversation.
4. WHEN a settings popover is open, Escape SHALL close the popover only, not the chat.

## Requirement 3: Settings behind the gear

1. THE answer language, plain-language and "Show how the AI works" settings SHALL live in a popover behind the gear.
2. WHEN the member minimizes and reopens, THE settings SHALL keep their values.
3. THE app SHALL NOT show Streamlit's "default value and Session State" warning for these settings.

## Requirement 4: Chat layout

1. WHILE there are no messages, THE chat SHALL show a greeting by first name and the suggested questions as chips.
2. WHEN the first question is asked, THE chips SHALL be hidden.
3. THE messages SHALL scroll inside the box, and THE message input SHALL stay pinned under them.
4. WHEN a new answer arrives, THE list SHALL scroll to it, and it SHALL appear in the same run as the question.
5. Read aloud SHALL be a compact control; pressing it while speaking SHALL stop the voice.

## Requirement 5: Small screens

1. WHILE the viewport is 760px wide or less, THE closed bar SHALL be a round icon button with an accessible name.
2. WHILE the viewport is 760px wide or less, THE open chat SHALL fill the screen.

## Requirement 6: Accessibility and safety

1. WHEN the chat opens, focus SHALL move to the message input; WHEN it minimizes or closes, focus SHALL return to the bar.
2. Icon-only buttons SHALL keep a text accessible name; tap targets SHALL be at least 44px.
3. Dock colours SHALL come from the RenewRight theme tokens (light, dark, system).
4. The newest answer SHALL stay a polite live region (unchanged from `c46c587`).
5. The dock script SHALL NOT read, write or send chat text; it may only move focus, scroll, and click minimize on Escape.
   Its only input SHALL be a fixed action word, validated in Python.
