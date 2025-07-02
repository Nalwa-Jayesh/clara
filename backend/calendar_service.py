import os
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleCalendarService:
    def __init__(self, credentials_path: str, calendar_id: str = 'primary'):
        """
        Initialize Google Calendar service
        
        Args:
            credentials_path: Path to service account JSON file
            calendar_id: Calendar ID to use (default: 'primary')
        """
        self.calendar_id = calendar_id
        self.service = self._authenticate(credentials_path)
        
    def _authenticate(self, credentials_path: str):
        """Authenticate using service account credentials"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise Exception(f"Failed to authenticate with Google Calendar: {str(e)}")
    
    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available"""
        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return len(events) == 0
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return False
    
    def get_available_slots(self, date: datetime, duration_minutes: int = 60, 
                          business_hours: tuple = (9, 17)) -> List[Dict[str, Any]]:
        """
        Get available time slots for a given date
        
        Args:
            date: Date to check
            duration_minutes: Duration of each slot
            business_hours: Tuple of (start_hour, end_hour) in 24h format
        """
        available_slots = []
        start_hour, end_hour = business_hours
        # Defensive: ensure duration_minutes is never None
        duration_minutes = duration_minutes or 60
        # Create timezone-aware datetime objects
        tz = pytz.timezone('Asia/Kolkata')  # Change to your timezone
        current_date = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        current_date = tz.localize(current_date) if current_date.tzinfo is None else current_date
        
        end_of_day = current_date.replace(hour=end_hour)
        
        while current_date < end_of_day:
            slot_end = current_date + timedelta(minutes=duration_minutes)
            
            if slot_end <= end_of_day and self.check_availability(current_date, slot_end):
                available_slots.append({
                    'start_time': current_date,
                    'end_time': slot_end,
                    'available': True
                })
            
            current_date += timedelta(minutes=30)  # 30-minute intervals
        
        return available_slots  # Return all available slots
    
    def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        attendee_email: Optional[str] = None,
        description: str = "",
    ) -> str:
        """Create a calendar event"""
        try:
            print("[DEBUG] Creating event with:")
            print("  Title:", title)
            print("  Start:", start_time, type(start_time), start_time.tzinfo)
            print("  End:", end_time, type(end_time), end_time.tzinfo)
            print("  Attendee:", attendee_email)
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
            }
            if attendee_email:
                event['attendees'] = [{'email': attendee_email}]
            print("[DEBUG] Event payload:", event)
            created_event = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event)
                .execute()
            )
            print("[DEBUG] Event created:", created_event)
            return created_event['id']
        except HttpError as error:
            print("[ERROR] Failed to create event:", error)
            raise Exception(f'Failed to create event: {error}')
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
        try:
            self.service.events().delete(
                calendarId=self.calendar_id, 
                eventId=event_id
            ).execute()
            return True
        except HttpError as error:
            print(f'Failed to delete event: {error}')
            return False
    
    def find_event(self, title=None, date=None, time=None):
        """Find an event by title, date, and/or time. Returns the first matching event if unique, or None if ambiguous or not found."""
        tz = pytz.timezone('Asia/Kolkata')
        if date:
            try:
                search_date = date if isinstance(date, datetime) else datetime.fromisoformat(date)
            except Exception:
                search_date = datetime.now(tz)
        else:
            search_date = datetime.now(tz)
        start_of_day = search_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        events = self.list_events(start_of_day, end_of_day)
        matches = []
        for event in events:
            # Match by title if provided
            if title and title.lower() not in event.get('summary', '').lower():
                continue
            # Match by time if provided
            if time:
                event_start = event['start'].get('dateTime')
                if event_start:
                    event_time = datetime.fromisoformat(event_start).strftime('%H:%M')
                    if event_time != time:
                        continue
            matches.append(event)
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            return None  # Ambiguous, let agent ask for clarification
        return None

    def list_events(self, start_date: datetime, end_date: datetime):
        """List all events between start_date and end_date"""
        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_date.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except Exception as e:
            print(f"[ERROR] Failed to list events: {e}")
            return []