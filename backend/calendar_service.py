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
    ) -> dict:
        """Create a calendar event and return event id and url"""
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
            return {
                'id': created_event['id'],
                'url': created_event.get('htmlLink', None)
            }
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
        # Ensure timezone-aware datetimes
        if search_date.tzinfo is None:
            search_date = tz.localize(search_date)
        else:
            search_date = search_date.astimezone(tz)
        start_of_day = search_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        events = self.list_events(start_of_day, end_of_day)
        matches = []
        for event in events:
            # Case-insensitive, partial title match
            if title:
                event_title = event.get('summary', '').lower()
                if title.lower() not in event_title:
                    continue
            # Flexible time match
            if time:
                event_start = event['start'].get('dateTime')
                if event_start:
                    event_dt = datetime.fromisoformat(event_start)
                    event_time_24 = event_dt.strftime('%H:%M')
                    event_time_12 = event_dt.strftime('%I:%M %p').lstrip('0')
                    # Accept both 24-hour and 12-hour (with or without AM/PM)
                    if not (
                        time == event_time_24 or
                        time == event_time_12 or
                        time in event_time_12 or
                        time in event_time_24
                    ):
                        continue
            matches.append(event)
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            return None  # Ambiguous, let agent ask for clarification
        return None

    def list_events(self, start_date: datetime, end_date: datetime):
        """List all events between start_date and end_date"""
        tz = pytz.timezone('Asia/Kolkata')
        # Ensure timezone-aware datetimes
        if start_date.tzinfo is None:
            start_date = tz.localize(start_date)
        else:
            start_date = start_date.astimezone(tz)
        if end_date.tzinfo is None:
            end_date = tz.localize(end_date)
        else:
            end_date = end_date.astimezone(tz)
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