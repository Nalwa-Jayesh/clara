# Clara Backend – AI Calendar Booking Assistant

This is the backend for Clara, an AI-powered calendar booking assistant. It provides a FastAPI server that integrates with Google Calendar and supports natural language booking, listing, and deletion of events.

---

## Features
- Book appointments via natural language
- List and delete calendar events
- Robust Google Calendar integration
- LLM-powered intent extraction (Gemini/GPT)
- REST API for frontend (Streamlit or other clients)

---

## Setup & Installation

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd clara/backend
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the `backend/` directory with the following:
```
GOOGLE_CREDENTIALS_PATH=backend/credentials.json  # Path to your Google service account JSON
GOOGLE_API_KEY=your_gemini_or_gpt_api_key
GOOGLE_CALENDAR_ID=primary  # Or your calendar's email
```

- The Google credentials file must be a service account with Calendar API access.
- For deployment (e.g., Render), use environment variables or secret files as described below.

### 4. Run the Backend Locally
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Deployment (e.g., Render)
- Set all environment variables in the Render dashboard or use a `render.yaml`.
- For Google credentials, use Render's Secret Files feature or write the file at startup from an env var.
- Use the following start command:
  ```
  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
  ```

---

## API Endpoints
- `POST /chat` — Main chat endpoint for booking, listing, and deleting events
- `GET /availability/{date}` — Get available slots for a date
- `DELETE /booking/{event_id}` — Cancel a booking
- `GET /` — Health check

---

## Google Calendar Setup
1. Create a Google Cloud project and enable the Calendar API.
2. Create a service account and download the credentials JSON.
3. Share your calendar with the service account email.
4. Set `GOOGLE_CREDENTIALS_PATH` to the path of this file.

---

## Notes
- All times are handled in Asia/Kolkata timezone by default (change in `calendar_service.py` if needed).
- The backend is designed to work with the Streamlit frontend in `../frontend`.

---

## License
MIT 