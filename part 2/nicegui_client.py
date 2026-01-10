#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import queue
import socket
import threading
from uuid import uuid4

from nicegui import ui

HOST = "127.0.0.1"  # Server IP (same PC)
PORT = 10000  # Server port


@dataclass
class SessionState:
    user_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""  # Display name from the input
    avatar: str = field(init=False)  # Avatar URL for this client
    messages: list[dict[str, str | bool]] = field(default_factory=list)  # UI list
    sock: socket.socket | None = None  # TCP socket
    connected: bool = False  # Connection status
    stop_event: threading.Event = field(default_factory=threading.Event)  # Thread stop flag
    inbox: "queue.Queue[tuple[str, bool, str]]" = field(default_factory=queue.Queue)  # Thread -> UI
    known_users: set[str] = field(default_factory=set)  # Names for the "to" list

    def __post_init__(self) -> None:
        self.avatar = f"https://robohash.org/{self.user_id}?bgset=bg2"


def now_stamp() -> str:
    # Current time for message stamp.
    return datetime.now().strftime("%H:%M:%S")


@ui.refreshable
def chat_messages(state: SessionState) -> None:
    # Draw all messages to the page.
    if state.messages:
        for msg in state.messages:
            if msg.get("kind") == "system":
                # Small center banner for join/leave.
                ui.label(f'{msg["text"]}  {msg["stamp"]}').classes(
                    "mx-auto my-2 text-xs bg-[#e6f4ea] text-[#1b4332] px-3 py-1 rounded-full shadow-sm"
                )
            else:
                ui.chat_message(
                    text=str(msg["text"]),
                    stamp=str(msg["stamp"]),
                    avatar=str(msg["avatar"]),
                    sent=bool(msg["sent"]),
                )
    else:
        ui.label("No messages yet").classes("mx-auto my-24 text-sm opacity-70")
    ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")


@ui.page("/")
async def main() -> None:
    state = SessionState()
    # Each browser tab gets its own SessionState.

    def add_message(text: str, sent: bool, avatar: str = "") -> None:
        # Ignore the hidden user-list message.
        if text.startswith("__users__ "):
            update_known_users(text)
            return
        # Convert join/leave to a system banner.
        kind = "chat"
        if text.endswith(" joined the chat"):
            name = text.rsplit(" joined the chat", 1)[0].strip()
            if name:
                text = f"user connect now : {name}"
                avatar = f"https://robohash.org/{name}?bgset=bg1"
                sent = False
                kind = "system"
        elif text.endswith(" left the chat"):
            kind = "system"
            sent = False
            avatar = ""
        state.messages.append(
            {
                "text": text,
                "stamp": now_stamp(),
                "sent": sent,
                "avatar": avatar,
                "kind": kind,
            }
        )
        update_known_users(text)
        chat_messages.refresh()

    def refresh_to_options() -> None:
        # Update the "to" dropdown and refresh it.
        to_select.options = sorted(state.known_users)
        to_select.value = []
        to_select.update()

    def update_known_users(text: str) -> None:
        # Update names we know about.
        updated = False
        if text.startswith("__users__ "):
            # Full list from the server (comma-separated).
            names = [n.strip() for n in text[len("__users__ "):].split(",") if n.strip()]
            state.known_users = {n for n in names if n != state.name}
            refresh_to_options()
            return
        if text.startswith("user connect now : "):
            name = text.split("user connect now : ", 1)[1].strip()
            if name and name != state.name:
                updated = name not in state.known_users
                state.known_users.add(name)
        elif text.endswith(" joined the chat"):
            name = text.rsplit(" joined the chat", 1)[0].strip()
            if name and name != state.name:
                updated = name not in state.known_users
                state.known_users.add(name)
        elif text.endswith(" left the chat"):
            name = text.rsplit(" left the chat", 1)[0].strip()
            if name in state.known_users:
                state.known_users.remove(name)
                updated = True
        elif " : " in text:
            sender, rest = text.split(" : ", 1)
            sender = sender.strip()
            if sender and sender != state.name:
                if sender not in state.known_users:
                    state.known_users.add(sender)
                    updated = True
            if " - " in rest:
                recipients_part = rest.split(" - ", 1)[0]
                for recipient in recipients_part.split(","):
                    recipient = recipient.strip()
                    if recipient and recipient != state.name:
                        if recipient not in state.known_users:
                            state.known_users.add(recipient)
                            updated = True

        if updated:
            refresh_to_options()

    def flush_inbox() -> None:
        # Pull messages from the background thread.
        while True:
            try:
                text, sent, avatar = state.inbox.get_nowait()
            except queue.Empty:
                break
            add_message(text, sent, avatar)

    def receiver() -> None:
        # Socket reader thread: receive from server.
        while not state.stop_event.is_set():
            try:
                data = state.sock.recv(1024) if state.sock else b""
            except OSError:
                break
            if not data:
                break
            text = data.decode("utf-8").strip()
            sender = text.split(" : ", 1)[0] if " : " in text else "user"
            avatar = f"https://robohash.org/{sender}?bgset=bg1"
            state.inbox.put((text, False, avatar))
        state.inbox.put(("disconnected from server", False, ""))
        state.connected = False

    def connect() -> None:
        if state.connected:
            return
        # Read name from input. If empty, make a default.
        name = (name_input.value or "").strip()
        if not name:
            name = f"user-{state.user_id[:6]}"
        state.name = name

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Read welcome + prompt.
            sock.recv(1024)
            sock.recv(1024)
            # Send our name.
            sock.sendall(name.encode("utf-8"))
        except OSError:
            add_message("connection failed", False, "")
            return

        state.sock = sock
        state.connected = True
        # Update status and reset list.
        status_label.text = f"online as {name}"
        state.stop_event.clear()
        state.known_users.clear()
        refresh_to_options()
        # Start background receiver.
        thread = threading.Thread(target=receiver, daemon=True)
        thread.start()

    def disconnect() -> None:
        if not state.connected:
            return
        # Tell the thread to stop and close socket.
        state.stop_event.set()
        if state.sock:
            try:
                state.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            state.sock.close()
        state.sock = None
        state.connected = False
        status_label.text = "offline"

    def send_message() -> None:
        # Send one message to selected users.
        if not state.connected or not state.sock:
            add_message("not connected", False, "")
            return
        selected = to_select.value or []
        recipients = ",".join(selected).strip()
        body = (message_input.value or "").strip()
        if not recipients or not body:
            add_message("use: name[,name] - message", False, "")
            return
        # Build the server format "name[,name] - text".
        payload = f"{recipients} - {body}"
        try:
            state.sock.sendall(payload.encode("utf-8"))
        except OSError:
            add_message("send failed", False, "")
            return
        # Local echo so the sender sees it immediately.
        add_message(f"{state.name} : {recipients} - {body}", True, state.avatar)
        message_input.value = ""

    ui.add_css(
        """
        a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}
        body {background: #f7f7f4;}
        """
    )

    # Periodic UI tick to drain the inbox.
    ui.timer(0.2, flush_inbox)

    with ui.column().classes("w-full max-w-2xl mx-auto items-stretch mt-10"):
        # NiceGUI needs the client connected before JS scroll.
        await ui.context.client.connected()
        chat_messages(state)

    with ui.footer().classes("bg-white"):
        with ui.column().classes("w-full max-w-3xl mx-auto my-6 gap-2"):
            with ui.row().classes("w-full no-wrap items-center gap-3"):
                with ui.avatar().on("click", lambda: ui.navigate.to(main)):
                    ui.image(state.avatar)
                # Name field.
                name_input = ui.input(placeholder="your name") \
                    .props("rounded outlined").classes("flex-grow")
                # "To" dropdown with connected users.
                to_select = ui.select(options=[], label="to", multiple=True) \
                    .props("rounded outlined").classes("flex-grow")
            with ui.row().classes("w-full no-wrap items-center gap-3"):
                # Message box + action buttons.
                message_input = ui.input(placeholder="message") \
                    .props("rounded outlined input-class=mx-3").classes("flex-grow")
                ui.button("Send", on_click=send_message)
                ui.button("Connect", on_click=connect)
                ui.button("Disconnect", on_click=disconnect)
                # Small status text.
                status_label = ui.label("offline").classes("text-xs")
            ui.markdown("simple chat app built with [NiceGUI](https://nicegui.io)") \
                .classes("text-xs self-end mr-8 m-[-1em] text-primary")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
