import os
import uuid
from datetime import datetime

from agent import CalendarBookingAgent
from calendar_service import GoogleCalendarService
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import BookingRequest, ChatResponse

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Calendar Booking AI Agent",
    description="Conversational AI agent for booking Google Calendar appointments",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for services
calendar_service = None
booking_agent = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global calendar_service, booking_agent

    try:
        # Get environment variables
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        api_key = os.getenv("GOOGLE_API_KEY")

        # Validate required environment variables
        if not credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH environment variable is required")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        if not os.path.exists(credentials_path):
            raise ValueError(f"Credentials file not found at: {credentials_path}")

        # Initialize Google Calendar service
        calendar_service = GoogleCalendarService(credentials_path, calendar_id)

        # Initialize booking agent
        booking_agent = CalendarBookingAgent(calendar_service, api_key)

        print("✅ Services initialized successfully")
        print(f"📁 Using credentials: {credentials_path}")
        print(f"📅 Using calendar ID: {calendar_id}")

    except Exception as e:
        print(f"❌ Failed to initialize services: {str(e)}")
        print("\n🔧 Please check your .env file contains:")
        print("   GOOGLE_CREDENTIALS_PATH=path/to/service-account-key.json")
        print("   GOOGLE_API_KEY=your_gemini_api_key")
        print("   GOOGLE_CALENDAR_ID=primary (optional)")
        raise


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Calendar Booking AI Agent is running!",
        "timestamp": datetime.now(),
        "status": "healthy",
        "calendar_service": "initialized" if calendar_service else "not_initialized",
        "booking_agent": "initialized" if booking_agent else "not_initialized",
    }


@app.get("/config")
async def get_config():
    """Get current configuration (without sensitive data)"""
    return {
        "calendar_id": os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        "credentials_path_exists": os.path.exists(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "")
        ),
        "api_key_configured": bool(os.getenv("GOOGLE_API_KEY")),
        "environment_loaded": True,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: BookingRequest):
    """Main chat endpoint for conversation"""
    global booking_agent

    if not booking_agent:
        raise HTTPException(
            status_code=500,
            detail="Booking agent not initialized. Please check your environment configuration.",
        )

    try:
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Process the message
        response = booking_agent.process_message(request.message, conversation_id)

        return ChatResponse(**response)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing message: {str(e)}"
        )


@app.get("/availability/{date}")
async def check_availability(date: str):
    """Check availability for a specific date"""
    global calendar_service

    if not calendar_service:
        raise HTTPException(
            status_code=500,
            detail="Calendar service not initialized. Please check your environment configuration.",
        )

    try:
        # Parse date
        from dateutil import parser

        target_date = parser.parse(date).date()
        target_datetime = datetime.combine(target_date, datetime.min.time())

        # Get available slots
        slots = calendar_service.get_available_slots(target_datetime)

        return {
            "date": date,
            "available_slots": [
                {
                    "start_time": slot["start_time"].isoformat(),
                    "end_time": slot["end_time"].isoformat(),
                    "available": slot["available"],
                }
                for slot in slots
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error checking availability: {str(e)}"
        )


@app.delete("/booking/{event_id}")
async def cancel_booking(event_id: str):
    """Cancel a booking"""
    global calendar_service

    if not calendar_service:
        raise HTTPException(
            status_code=500,
            detail="Calendar service not initialized. Please check your environment configuration.",
        )

    try:
        success = calendar_service.delete_event(event_id)
        if success:
            return {"message": "Booking cancelled successfully", "event_id": event_id}
        else:
            raise HTTPException(
                status_code=404, detail="Event not found or couldn't be deleted"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error cancelling booking: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
