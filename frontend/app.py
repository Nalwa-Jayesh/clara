import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="📅 Calendar Booking Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Improved custom CSS for modern look and better readability
st.markdown(
    """
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        font-size: 1.08rem;
    }
    .user-message {
        background: linear-gradient(90deg, #1976d2 60%, #2196f3 100%);
        color: #fff;
        border-left: 4px solid #1565c0;
        font-weight: 500;
    }
    .assistant-message {
        background: linear-gradient(90deg, #7c3aed 60%, #a78bfa 100%);
        color: #fff;
        border-left: 4px solid #5b21b6;
        font-weight: 500;
    }
    .booking-confirmed {
        background: #bbf7d0 !important;
        color: #14532d !important;
        border: 2px solid #22c55e !important;
        border-radius: 14px !important;
        padding: 1.2rem !important;
        margin: 1.2rem 0 !important;
        box-shadow: 0 4px 16px rgba(34,197,94,0.08);
        font-size: 1.08rem;
    }
    .booking-confirmed h3 {
        color: #166534 !important;
        font-size: 1.4rem;
        margin-bottom: 0.7rem;
    }
    .booking-confirmed p {
        color: #14532d !important;
        font-size: 1.08rem;
        margin: 0.2rem 0;
    }
    .booking-confirmed strong {
        color: #166534 !important;
    }
    .stButton > button {
        width: 100%;
        border-radius: 20px;
        border: none;
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        font-weight: 600;
    }
    .stTextInput > div > input {
        border-radius: 8px;
        border: 1.5px solid #a78bfa;
        padding: 0.5rem 1rem;
    }
    .booking-confirmed .event-id-box {
        background: #18181b;
        color: #f3e8ff;
        border-radius: 8px;
        padding: 0.7rem 1.2rem;
        margin-top: 1.1rem;
        font-family: 'Fira Mono', 'Consolas', 'Menlo', monospace;
        font-size: 1.08rem;
        display: flex;
        align-items: center;
        gap: 0.7rem;
        word-break: break-all;
        box-shadow: 0 2px 8px rgba(0,0,0,0.10);
        border: 1.5px solid #a21caf;
    }
    .event-id-label {
        background: #a21caf;
        color: #fff;
        border-radius: 6px;
        padding: 0.2rem 0.9rem;
        font-weight: bold;
        font-size: 1.02rem;
        margin-right: 0.7rem;
        letter-spacing: 0.04em;
        display: inline-block;
        box-shadow: 0 1px 4px rgba(162,28,175,0.10);
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_status" not in st.session_state:
    st.session_state.api_status = "unknown"

if "pending_user_input" not in st.session_state:
    st.session_state.pending_user_input = None


def check_api_status():
    """Check if the backend API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=10)
        return response.status_code == 200
    except:
        return False


def send_message(message: str) -> Dict[str, Any]:
    """Send message to the backend API"""
    try:
        payload = {
            "message": message,
            "conversation_id": st.session_state.conversation_id,
        }

        response = requests.post(f"{API_BASE_URL}/chat", json=payload, timeout=60)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "message": f"Error: {response.status_code} - {response.text}",
                "requires_input": True,
            }

    except requests.exceptions.RequestException as e:
        return {
            "message": f"Connection error: {str(e)}. Please make sure the backend server is running.",
            "requires_input": True,
        }


def display_message(message: Dict[str, Any], is_user: bool = False):
    """Display a chat message"""
    css_class = "user-message" if is_user else "assistant-message"
    icon = "👤" if is_user else "🤖"

    st.markdown(
        f"""
    <div class="chat-message {css_class}">
        <strong>{icon} {"You" if is_user else "Assistant"}:</strong><br>
        {message.get("content", message.get("message", "")).replace("\n", "<br>")}
    </div>
    """,
        unsafe_allow_html=True,
    )


def display_booking_confirmation(booking: Dict[str, Any]):
    """Display booking confirmation"""
    attendee_html = f'<p><strong>📧 Attendee:</strong> {booking["attendee_email"]}</p>' if booking.get("attendee_email") else ''
    html = (
        '<div class="booking-confirmed">'
        '<h3>✅ Booking Confirmed!</h3>'
        f'<p><strong>📋 Title:</strong> {booking["title"]}</p>'
        f'<p><strong>📅 Date & Time:</strong> {booking["start_time"]}</p>'
        f'<p><strong>🕐 Duration:</strong> {booking["start_time"]} - {booking["end_time"]}</p>'
        f'{attendee_html}'
        '<div class="event-id-box">'
        '<span class="event-id-label">ID</span>'
        f'<span>{booking["event_id"]}</span>'
        '</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def display_time_slots(slots: List[Dict[str, Any]], message_id=None):
    """Display available time slots"""
    if slots:
        st.markdown("### 🕐 Available Time Slots:")
        for i, slot in enumerate(slots[:5]):  # Show max 5 slots
            start_time = datetime.fromisoformat(
                slot["start_time"].replace("Z", "+00:00")
            )
            end_time = datetime.fromisoformat(slot["end_time"].replace("Z", "+00:00"))

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(
                    f"**{start_time.strftime('%I:%M %p')} - {
                        end_time.strftime('%I:%M %p')
                    }**"
                )
            with col2:
                slot_key = f"slot_{i}_{start_time.isoformat()}_{end_time.isoformat()}"
                if message_id:
                    slot_key = f"{slot_key}_{message_id}"
                if st.button("Select", key=slot_key):
                    # Send booking request for this slot with date and time
                    booking_message = f"Book the slot on {start_time.strftime('%Y-%m-%d')} at {start_time.strftime('%I:%M %p')}"
                    st.session_state.pending_user_input = booking_message


def handle_user_input(user_input: str):
    """Handle user input and get AI response"""
    if not user_input.strip():
        return

    # Add user message to session state
    st.session_state.messages.append(
        {"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()}
    )

    # --- Auto-log conversation in sidebar ---
    # Use conversation_id as chat_id
    chat_id = st.session_state.conversation_id
    if "chats" not in st.session_state:
        st.session_state.chats = {}
    if chat_id not in st.session_state.chats:
        st.session_state.chats[chat_id] = []
    st.session_state.chats[chat_id].append({
        "role": "user", "content": user_input, "timestamp": datetime.now().isoformat()
    })
    st.session_state.selected_chat_id = chat_id
    # --- End auto-log ---

    # Get AI response
    with st.spinner("🤖 Thinking..."):
        response = send_message(user_input)

    # Add AI response to session state
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.get("message", ""),
            "timestamp": datetime.now().isoformat(),
            "suggested_slots": response.get("suggested_slots"),
            "booking_confirmed": response.get("booking_confirmed"),
        }
    )
    # --- Auto-log assistant message in sidebar ---
    st.session_state.chats[chat_id].append({
        "role": "assistant",
        "content": response.get("message", ""),
        "timestamp": datetime.now().isoformat(),
        "suggested_slots": response.get("suggested_slots"),
        "booking_confirmed": response.get("booking_confirmed"),
    })
    # --- End auto-log ---

    # If the response contains a list of appointments/events, display them with delete buttons
    if "appointments" in response:
        display_events_with_delete(response["appointments"])


def delete_event(event_id):
    response = requests.delete(f"{API_BASE_URL}/booking/{event_id}")
    return response.status_code == 200


def display_events_with_delete(events):
    st.markdown("### 📅 Your Appointments:")
    for event in events:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{event.get('summary', 'Untitled')}**")
            st.write(f"{event['start'].get('dateTime', '')} - {event['end'].get('dateTime', '')}")
        with col2:
            if st.button("Delete", key=f"delete_{event['id']}"):
                if delete_event(event['id']):
                    st.success("Event deleted!")
                    st.experimental_rerun()
                else:
                    st.error("Failed to delete event.")


def render_sidebar():
    """Render the sidebar content"""
    with st.sidebar:
        st.header("🔧 Settings")

        # API Status
        api_status = check_api_status()
        status_color = "🟢" if api_status else "🔴"
        status_text = "Connected" if api_status else "Disconnected"
        st.markdown(f"**Backend Status:** {status_color} {status_text}")

        st.divider()

        # Chat Conversations
        st.subheader("💬 Chats")
        if "chats" not in st.session_state:
            st.session_state.chats = {}
        if "selected_chat_id" not in st.session_state:
            st.session_state.selected_chat_id = None

        # List all chats
        for chat_id in list(st.session_state.chats.keys()):
            col1, col2 = st.columns([6, 1])
            with col1:
                if st.button(f"Chat {chat_id[:8]}", key=f"select_{chat_id}"):
                    st.session_state.selected_chat_id = chat_id
            with col2:
                if st.button("🗑️", key=f"delete_{chat_id}"):
                    del st.session_state.chats[chat_id]
                    if st.session_state.selected_chat_id == chat_id:
                        st.session_state.selected_chat_id = None
                    st.rerun()

        st.divider()

        # Conversation Info for selected chat
        if st.session_state.selected_chat_id:
            chat_id = st.session_state.selected_chat_id
            messages = st.session_state.chats.get(chat_id, [])
            st.subheader("📝 Conversation Info")
            st.write(f"**ID:** `{chat_id[:8]}...`")
            st.write(f"**Messages:** {len(messages)}")

        return api_status


def render_stats_panel():
    """Render the stats panel"""
    st.subheader("📊 Quick Stats")

    # Display some quick stats
    total_messages = len(st.session_state.messages)
    user_messages = len([m for m in st.session_state.messages if m["role"] == "user"])

    st.metric("Total Messages", total_messages)
    st.metric("Your Messages", user_messages)

    # Show recent bookings count
    confirmed_bookings = len(
        [
            m
            for m in st.session_state.messages
            if m["role"] == "assistant" and m.get("booking_confirmed")
        ]
    )
    st.metric("Bookings Made", confirmed_bookings)

    st.divider()

    # Calendar preview (mock)
    st.subheader("📅 Today's Preview")
    current_time = datetime.now()

    # Show next few hours as example
    for i in range(3):
        time_slot = current_time + timedelta(hours=i + 1)
        st.write(f"**{time_slot.strftime('%I:%M %p')}** - Available")


# Main UI
def main():
    st.markdown(
        """
        <div class="main-header">
            <h1>📅 AI Calendar Booking Assistant</h1>
            <p>Chat with me to book your appointments easily!</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_status = render_sidebar()

    if st.session_state.pending_user_input:
        handle_user_input(st.session_state.pending_user_input)
        st.session_state.pending_user_input = None
        st.rerun()

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("💬 Chat")
        chat_container = st.container()
        with chat_container:
            for idx, message in enumerate(st.session_state.messages):
                is_user = message["role"] == "user"
                display_message(message, is_user)
                # Only show slots if this assistant message has suggested_slots and no booking_confirmed
                if not is_user and message.get("suggested_slots") and not message.get("booking_confirmed"):
                    display_time_slots(message["suggested_slots"], message_id=idx)
                if not is_user and message.get("booking_confirmed"):
                    display_booking_confirmation(message["booking_confirmed"])

    with col2:
        render_stats_panel()

    # ✅ Place chat_input here, OUTSIDE layout blocks
    if api_status:
        user_input = st.chat_input("Type your message here...")
        if user_input:
            handle_user_input(user_input)
            st.rerun()
    else:
        st.error("Please start the backend server to begin chatting.")


if __name__ == "__main__":
    main()
