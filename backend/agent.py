import json
from datetime import datetime, timedelta
from typing import Any, Dict
import re

from calendar_service import GoogleCalendarService
from dateutil import parser
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, Graph
from models import BookingConfirmation, TimeSlot


class CalendarBookingAgent:
    def __init__(self, calendar_service: GoogleCalendarService, api_key: str):
        self.calendar_service = calendar_service
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro", google_api_key=api_key, temperature=0.7
        )
        self.memory = ConversationBufferMemory(return_messages=True)
        self.conversations = {}  # Store conversation states

        # Create the conversation graph
        self.graph = self._create_graph()

    def _create_graph(self):
        """Create the LangGraph conversation flow"""

        WORK_START_HOUR = 9
        WORK_END_HOUR = 17

        def is_within_working_hours(hour, minute):
            return WORK_START_HOUR <= hour < WORK_END_HOUR

        def preprocess_date(date_str):
            today = datetime.now().date()
            if isinstance(date_str, str):
                if date_str.lower() == "today":
                    return today.isoformat()
                elif date_str.lower() == "tomorrow":
                    return (today + timedelta(days=1)).isoformat()
                # If it's a weekday name, handle accordingly (optional)
                try:
                    parsed = parser.parse(date_str).date()
                    if parsed < today:
                        # If the LLM returned a past date, fallback to tomorrow
                        return (today + timedelta(days=1)).isoformat()
                    return parsed.isoformat()
                except Exception:
                    return today.isoformat()
            return date_str

        def understand_intent(state):
            print("[DEBUG][Agent] Entered understand_intent")
            """Analyze user intent and extract booking information"""
            message = state["message"]
            conversation_history = state.get("history", [])

            # Build context from conversation history
            context = ""
            if conversation_history:
                context = "Previous conversation:\n"
                for msg in conversation_history[-4:]:  # Last 4 messages
                    context += f"{msg['role']}: {msg['content']}\n"

            prompt = f"""You are an AI assistant specialized in analyzing booking and appointment requests.

{context}Current user message: "{message}"

Analyze the message to determine the user's intent and extract booking details. Consider context from previous messages if available.

INTENT CATEGORIES:
- book_appointment: User wants to schedule a new appointment
- check_availability: User is asking about available time slots
- modify_booking: User wants to change an existing appointment
- cancel_booking: User wants to cancel an existing appointment (extract as much info as possible to identify the event: event_id, title, date, time. If the user says 'last meeting', set event_id to 'last')
- reschedule_booking: User wants to move an appointment to a different time
- general_inquiry: Questions about booking process, policies, or general chat
- list_appointments: User wants to list appointments for a specific date

EXTRACTION GUIDELINES:
- Date: Parse relative dates (today, tomorrow, next week, Monday, Friday, next Monday, etc.) and convert to YYYY-MM-DD. If the user says a weekday (e.g., 'Friday'), return the next occurrence of that weekday in YYYY-MM-DD format. If the user says 'today', 'tomorrow', or a weekday, return those exact words in the 'date' field, not a specific date.
- Time: Handle various formats (2pm, 14:00, 2:30 PM, afternoon, morning, etc.)
- Duration: Look for explicit mentions or infer from context (default: 60 minutes)
- Title: Extract explicit titles or infer from context (meeting, consultation, appointment, etc.)
- Email: Extract any email addresses mentioned
- For cancel_booking: Extract as much info as possible to identify the event (event_id, title, date, time). If the user says 'last meeting', set event_id to 'last'.

RESPONSE FORMAT (JSON only):
{{
    "intent": "one of the categories above",
    "extracted_info": {{
        "date": "YYYY-MM-DD or null or a relative string like 'today', 'tomorrow', or a weekday",
        "time": "HH:MM (24-hour format) or null",
        "duration": "integer minutes",
        "title": "string or null",
        "attendee_email": "valid email or null",
        "event_id": "string or null",
        "additional_notes": "any special requirements or notes"
    }},
    "needs_clarification": ["array of missing critical information"],
    "confidence": "float between 0.0-1.0",
    "reasoning": "brief explanation of the analysis"
}}

Important: Return ONLY the JSON object, no additional text or formatting. Always return the date in YYYY-MM-DD format for absolute dates, or as 'today', 'tomorrow', or a weekday for relative dates."""

            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                print("[DEBUG][Agent] Raw LLM response:", response.content)
                content = response.content.strip()
                if content.startswith('```json'):
                    content = content[len('```json'):].strip()
                if content.startswith('```'):
                    content = content[len('```'):].strip()
                if content.endswith('```'):
                    content = content[:-3].strip()
                result = json.loads(content)

                state["intent"] = result["intent"]
                state["extracted_info"] = result["extracted_info"]
                state["needs_clarification"] = result["needs_clarification"]
                state["confidence"] = result["confidence"]

                print("[DEBUG][Agent] LLM extracted:", result)

            except Exception as e:
                print("[DEBUG][Agent] Exception in LLM extraction:", e)
                # Fallback for parsing errors
                state["intent"] = "general_inquiry"
                state["extracted_info"] = {}
                state["needs_clarification"] = ["date", "time"]
                state["confidence"] = 0.5

            return state

        def check_availability_and_suggest(state):
            """Check calendar availability and suggest time slots"""
            extracted_info = state["extracted_info"]

            # Debug: print what the LLM extracted for the date
            print(f"[DEBUG] LLM extracted date: {extracted_info.get('date')}")

            # Preprocess relative dates and ambiguous dates
            if "date" in extracted_info and extracted_info["date"]:
                extracted_info["date"] = preprocess_date(extracted_info["date"])
                print(f"[DEBUG] Preprocessed date: {extracted_info['date']}")

            # Parse date
            target_date = None
            if extracted_info.get("date"):
                try:
                    target_date = parser.parse(extracted_info["date"]).date()
                except:
                    target_date = datetime.now().date() + timedelta(days=1)
            else:
                target_date = datetime.now().date() + timedelta(days=1)

            # Get duration
            duration = extracted_info.get("duration", 60)

            # Get available slots
            target_datetime = datetime.combine(
                target_date, datetime.min.time())
            available_slots = self.calendar_service.get_available_slots(
                target_datetime, duration
            )

            # Check if requested slot is available
            requested_time = extracted_info.get("time")
            requested_slot_available = False
            requested_slot = None
            requested_time_within_hours = True
            if requested_time:
                try:
                    requested_hour, requested_minute = map(int, requested_time.split(':'))
                    if not is_within_working_hours(requested_hour, requested_minute):
                        requested_time_within_hours = False
                    for slot in available_slots:
                        if (slot["start_time"].hour == requested_hour and slot["start_time"].minute == requested_minute):
                            requested_slot_available = True
                            requested_slot = slot
                            break
                except Exception as e:
                    pass

            state["available_slots"] = available_slots
            state["target_date"] = target_date.isoformat()
            state["requested_slot_available"] = requested_slot_available
            state["requested_slot"] = requested_slot
            state["requested_time_within_hours"] = requested_time_within_hours

            return state

        def generate_response(state):
            """Generate natural language response"""
            intent = state["intent"]
            needs_clarification = state.get("needs_clarification", [])
            available_slots = state.get("available_slots", [])
            requested_slot_available = state.get("requested_slot_available", False)
            requested_time_within_hours = state.get("requested_time_within_hours", True)

            # Remove attendee_email from needs_clarification to make it optional
            if "attendee_email" in needs_clarification:
                needs_clarification = [item for item in needs_clarification if item != "attendee_email"]
                state["needs_clarification"] = needs_clarification

            if intent == "book_appointment":
                if needs_clarification:
                    if "date" in needs_clarification:
                        state["response"] = (
                            "I'd be happy to help you book an appointment! What date would you prefer?"
                        )
                    elif "time" in needs_clarification and available_slots:
                        slots_text = "\n".join(
                            [
                                f"• {slot['start_time'].strftime('%I:%M %p')} - {slot['end_time'].strftime('%I:%M %p')}"
                                for slot in available_slots[:3]
                            ]
                        )
                        state["response"] = (
                            f"Here are some available time slots for {state['target_date']}:\n"
                            f"{slots_text}\n\n"
                            "Which time works best for you?"
                        )
                    else:
                        state["response"] = (
                            "Could you please provide the date and preferred time for your appointment?"
                        )
                else:
                    if not requested_time_within_hours:
                        state["response"] = (
                            f"❌ The requested time is outside working hours ({WORK_START_HOUR}:00 - {WORK_END_HOUR}:00). "
                            "Please choose a time within working hours."
                        )
                    elif requested_slot_available:
                        # All info available, requested slot is available, proceed to booking
                        state["response"] = (
                            "Perfect! The requested slot is available. Let me confirm your appointment booking."
                        )
                        state["ready_to_book"] = True
                    else:
                        # Requested slot not available, show alternatives
                        slots_text = "\n".join(
                            [
                                f"• {slot['start_time'].strftime('%I:%M %p')} - {slot['end_time'].strftime('%I:%M %p')}"
                                for slot in available_slots
                            ]
                        )
                        state["response"] = (
                            "❌ The requested time slot is not available. Here are some available time slots:\n"
                            f"{slots_text}\n\n"
                            "Which time works best for you?"
                        )

            elif intent == "check_availability":
                if available_slots:
                    slots_text = "\n".join(
                        [
                            f"• {slot['start_time'].strftime('%I:%M %p')} - {slot['end_time'].strftime('%I:%M %p')}"
                            for slot in available_slots
                        ]
                    )
                    state["response"] = (
                        f"Here are the available time slots:\n{slots_text}"
                    )
                else:
                    state["response"] = (
                        "I don't see any available slots for that time. Would you like to try a different date?"
                    )

            elif intent == "list_appointments":
                extracted_info = state.get("extracted_info", {})
                date = extracted_info.get("date")
                from dateutil import parser
                import pytz
                tz = pytz.timezone('Asia/Kolkata')
                if date:
                    try:
                        target_date = parser.parse(date).date()
                    except Exception:
                        target_date = datetime.now(tz).date()
                else:
                    target_date = datetime.now(tz).date()
                start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
                end_of_day = start_of_day + timedelta(days=1)
                events = self.calendar_service.list_events(start_of_day, end_of_day)
                if not events:
                    return {
                        "message": "You have no appointments for that day.",
                        "conversation_id": state["conversation_id"],
                        "requires_input": False,
                    }
                # Store mapping of event names (and optionally date/time) to event IDs in conversation context
                name_to_id = {}
                event_lines = []
                for event in events:
                    summary = event.get('summary', 'Untitled')
                    start = event['start'].get('dateTime', '')
                    end = event['end'].get('dateTime', '')
                    event_id = event.get('id', '')
                    # Use (summary, start) as key for uniqueness
                    name_to_id[(summary.lower(), start)] = event_id
                    event_lines.append(f"• {summary} (ID: {event_id}): {start} - {end}")
                # Save mapping in conversation context
                conversation = self.conversations[state["conversation_id"]]
                if "context" not in conversation:
                    conversation["context"] = {}
                conversation["context"]["name_to_id"] = name_to_id
                response_text = "Here are your appointments for the day:\n" + "\n".join(event_lines)
                return {
                    "message": response_text,
                    "conversation_id": state["conversation_id"],
                    "requires_input": False,
                }

            else:
                state["response"] = (
                    "Hello! I'm here to help you book appointments. What date and time would you like to schedule your meeting?"
                )

            return state

        def book_appointment(state):
            """Actually book the appointment"""
            extracted_info = state["extracted_info"]
            available_slots = state.get("available_slots", [])
            requested_slot_available = state.get("requested_slot_available", False)
            requested_slot = state.get("requested_slot")

            if not available_slots:
                state["response"] = "Sorry, no available slots found. Please try a different time."
                return state

            requested_time = extracted_info.get("time")
            target_slot = None
            exact_match_found = False

            if requested_slot_available and requested_slot:
                target_slot = requested_slot
                exact_match_found = True
            else:
                # Book the closest available slot or show alternatives
                best_match = None
                min_time_diff = float('inf')
                if requested_time:
                    try:
                        requested_hour, requested_minute = map(int, requested_time.split(':'))
                        for slot in available_slots:
                            slot_minutes = slot["start_time"].hour * 60 + slot["start_time"].minute
                            requested_minutes = requested_hour * 60 + requested_minute
                            time_diff = abs(slot_minutes - requested_minutes)
                            if time_diff < min_time_diff:
                                min_time_diff = time_diff
                                best_match = slot
                        target_slot = best_match
                    except Exception as e:
                        target_slot = available_slots[0]
                else:
                    target_slot = available_slots[0]

            if not target_slot:
                state["response"] = "Sorry, I couldn't find a suitable time slot."
                return state

            start_time = target_slot["start_time"]
            end_time = target_slot["end_time"]

            # Rest of your booking logic...
            title = extracted_info.get("title")
            if not title:
                user_message = state.get("message", "").lower()
                for keyword in ["meeting", "call", "appointment", "event"]:
                    if keyword in user_message:
                        title = keyword.capitalize()
                        break
                if not title:
                    title = "Meeting"

            attendee_email = extracted_info.get("attendee_email")

            try:
                event_info = self.calendar_service.create_event(
                    title=title,
                    start_time=start_time,
                    end_time=end_time,
                    attendee_email=attendee_email,
                    description="Booked via AI Assistant",
                )

                state["booking_confirmed"] = {
                    "event_id": event_info["id"],
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "attendee_email": attendee_email,
                    "event_url": event_info.get("url"),
                }

                # Compose response
                if exact_match_found:
                    state["response"] = f"✅ Appointment booked successfully!\n\n📅 {title}\n🕐 {start_time.strftime('%B %d, %Y at %I:%M %p')} - {end_time.strftime('%I:%M %p')}"
                else:
                    state["response"] = (
                        f"❌ The requested time slot ({requested_time}) is not available.\n"
                        f"✅ Booked the closest available slot instead.\n\n"
                        f"📅 {title}\n🕐 {start_time.strftime('%B %d, %Y at %I:%M %p')} - {end_time.strftime('%I:%M %p')}"
                    )
                if attendee_email:
                    state["response"] += f"\n📧 Invitation sent to {attendee_email}"

            except Exception as e:
                state["response"] = f"Sorry, I couldn't book the appointment. Error: {str(e)}"

            return state

        # Define the graph
        workflow = Graph()

        # Add nodes
        workflow.add_node("understand_intent", understand_intent)
        workflow.add_node("check_availability", check_availability_and_suggest)
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("book_appointment", book_appointment)

        # Add edges
        workflow.add_edge("understand_intent", "check_availability")
        workflow.add_edge("check_availability", "generate_response")

        # Conditional edge for booking
        def should_book(state):
            return "book_appointment" if state.get("ready_to_book") else END

        workflow.add_conditional_edges("generate_response", should_book)
        workflow.add_edge("book_appointment", END)

        # Set entry point
        workflow.set_entry_point("understand_intent")

        return workflow.compile()

    def process_message(self, message: str, conversation_id: str) -> Dict[str, Any]:
        """Process a user message and return response"""

        # Get or create conversation state
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {"history": [], "context": {}}

        conversation = self.conversations[conversation_id]

        # Add user message to history
        conversation["history"].append(
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Prepare state for the graph
        state = {
            "message": message,
            "history": conversation["history"],
            "conversation_id": conversation_id,
        }

        # Run the conversation graph
        try:
            result = self.graph.invoke(state)

            # Determine the assistant's reply for history
            assistant_reply = result.get("response") or result.get("message", "")

            conversation["history"].append(
                {
                    "role": "assistant",
                    "content": assistant_reply,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Handle list appointments intent
            if result.get("intent") == "list_appointments":
                extracted_info = result.get("extracted_info", {})
                date = extracted_info.get("date")
                from dateutil import parser
                import pytz
                tz = pytz.timezone('Asia/Kolkata')
                if date:
                    try:
                        target_date = parser.parse(date).date()
                    except Exception:
                        target_date = datetime.now(tz).date()
                else:
                    target_date = datetime.now(tz).date()
                start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
                end_of_day = start_of_day + timedelta(days=1)
                events = self.calendar_service.list_events(start_of_day, end_of_day)
                if not events:
                    return {
                        "message": "You have no appointments for that day.",
                        "conversation_id": conversation_id,
                        "requires_input": False,
                    }
                # Store mapping of event names (and optionally date/time) to event IDs in conversation context
                name_to_id = {}
                event_lines = []
                for event in events:
                    summary = event.get('summary', 'Untitled')
                    start = event['start'].get('dateTime', '')
                    end = event['end'].get('dateTime', '')
                    event_id = event.get('id', '')
                    # Use (summary, start) as key for uniqueness
                    name_to_id[(summary.lower(), start)] = event_id
                    event_lines.append(f"• {summary} (ID: {event_id}): {start} - {end}")
                # Save mapping in conversation context
                conversation = self.conversations[conversation_id]
                if "context" not in conversation:
                    conversation["context"] = {}
                conversation["context"]["name_to_id"] = name_to_id
                response_text = "Here are your appointments for the day:\n" + "\n".join(event_lines)
                return {
                    "message": response_text,
                    "conversation_id": conversation_id,
                    "requires_input": False,
                }

            # Handle cancel_booking intent (generalized deletion)
            if result.get("intent") == "cancel_booking":
                extracted_info = result.get("extracted_info", {})
                event_id = extracted_info.get("event_id")
                title = extracted_info.get("title")
                date = extracted_info.get("date")
                time = extracted_info.get("time")
                # Try to resolve event_id from mapping if only title (and optionally date/time) is given
                if not event_id and title:
                    conversation = self.conversations[conversation_id]
                    name_to_id = conversation.get("context", {}).get("name_to_id", {})
                    # Try to match by title (case-insensitive, most recent occurrence)
                    matched_id = None
                    matched_key = None
                    for (event_title, event_start), eid in name_to_id.items():
                        if title.lower() in event_title:
                            # If date/time is provided, try to match start time as well
                            if date or time:
                                if date and date in event_start:
                                    matched_id = eid
                                    matched_key = (event_title, event_start)
                                    break
                                if time and time in event_start:
                                    matched_id = eid
                                    matched_key = (event_title, event_start)
                                    break
                            else:
                                matched_id = eid
                                matched_key = (event_title, event_start)
                                break
                    if matched_id:
                        event_id = matched_id
                # If event_id is 'last', get the most recent event
                if event_id == "last":
                    last_event = self.calendar_service.find_event()
                    if last_event:
                        event_id = last_event.get("id")
                    else:
                        return {
                            "message": "I couldn't find any recent meeting to delete.",
                            "conversation_id": conversation_id,
                            "requires_input": False,
                        }
                # If event_id is not provided, try to find by title/date/time
                if not event_id:
                    found_event = self.calendar_service.find_event(title=title, date=date, time=time)
                    if found_event:
                        event_id = found_event.get("id")
                    else:
                        return {
                            "message": "I couldn't find a meeting matching your description. Please provide more details or the event ID.",
                            "conversation_id": conversation_id,
                            "requires_input": True,
                        }
                # Try to delete the event
                try:
                    deleted = self.calendar_service.delete_event(event_id)
                    if deleted:
                        return {
                            "message": f"✅ Meeting deleted successfully! (ID: {event_id})",
                            "conversation_id": conversation_id,
                            "requires_input": False,
                        }
                    else:
                        return {
                            "message": f"I couldn't delete the meeting. Please check the event ID or try again.",
                            "conversation_id": conversation_id,
                            "requires_input": True,
                        }
                except Exception as e:
                    return {
                        "message": f"Sorry, I couldn't delete the meeting. Error: {str(e)}",
                        "conversation_id": conversation_id,
                        "requires_input": True,
                    }

            # Prepare response
            response = {
                "message": result.get("response", result.get("message", "")),
                "conversation_id": conversation_id,
                "requires_input": not result.get("booking_confirmed"),
            }

            # Add suggested slots if available
            if result.get("available_slots"):
                response["suggested_slots"] = [
                    TimeSlot(
                        start_time=slot["start_time"],
                        end_time=slot["end_time"],
                        available=slot["available"],
                    )
                    for slot in result["available_slots"]
                ]

            # Add booking confirmation if available
            if result.get("booking_confirmed"):
                booking = result["booking_confirmed"]
                response["booking_confirmed"] = BookingConfirmation(
                    event_id=booking["event_id"],
                    title=booking["title"],
                    start_time=booking["start_time"],
                    end_time=booking["end_time"],
                    attendee_email=booking.get("attendee_email"),
                    event_url=booking.get("event_url"),
                )

            return response

        except Exception as e:
            # Fallback response
            return {
                "message": f"I apologize, but I encountered an error processing your request. Please try again. Error: {str(e)}",
                "conversation_id": conversation_id,
                "requires_input": True,
            }