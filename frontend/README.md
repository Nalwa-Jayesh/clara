# Clara Frontend – AI Calendar Booking Assistant

This is the frontend for Clara, an AI-powered calendar booking assistant. It provides a modern Streamlit UI for chatting with the backend, booking appointments, listing, and deleting calendar events.

---

## Features
- Chat-based interface for booking, listing, and deleting events
- Modern, responsive UI with chat history and sidebar
- Displays booking confirmations, event IDs, and Google Calendar links
- Supports both local and cloud (Streamlit Cloud) deployment

---

## Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Nalwa-Jayesh/clara.git
cd clara/frontend
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Backend URL

#### Local Development
- Create a `.env` file in the `frontend/` directory:
  ```
  API_BASE_URL=http://localhost:8000
  ```
- The app will use this value to connect to your backend.

#### Streamlit Cloud Deployment
- Go to your app's dashboard → **Settings** → **Secrets**.
- Add the following in TOML format:
  ```toml
  API_BASE_URL = "https://your-backend-url.onrender.com"
  ```
- The app will use `st.secrets["API_BASE_URL"]` automatically.

---

## Running the App

### Local
```bash
streamlit run app.py
```
- The app will open in your browser at `http://localhost:8501` by default.

### Streamlit Cloud
- Push your code to GitHub.
- Deploy via [Streamlit Cloud](https://share.streamlit.io/).
- Set your secrets as above.

---

## Notes
- The frontend is designed to work with the backend in `../backend`.
- Make sure the backend is running and accessible at the URL you set in `API_BASE_URL`.
- For best results, deploy the backend first, then update the frontend's API URL.

---

## License
MIT 