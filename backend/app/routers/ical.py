"""iCal feed generation for calendar reservations."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from datetime import datetime, timezone
from icalendar import Calendar, Event
from app.services.calendar_service import CalendarService
from app.cache import get_cache, RedisCache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/calendar",
    tags=["ical"]
)


async def get_calendar_service_with_cache() -> tuple[CalendarService, Optional[RedisCache]]:
    """Get CalendarService instance with Redis client."""
    cache = get_cache()
    redis_client = cache.client if cache and cache._connected else None
    calendar_service = CalendarService(redis_client=redis_client)
    return calendar_service, cache


def parse_event_datetime(event_datetime: dict) -> datetime:
    """Parse datetime from Google Calendar event format."""
    dt_str = event_datetime.get('dateTime')
    if dt_str:
        # Parse ISO format datetime
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt
    return datetime.now(timezone.utc)


def extract_indicatif_from_summary(summary: str) -> str:
    """Extract vehicle indicatif from event summary.
    
    Format: {indicatif} - {chauffeur} - {mission}
    """
    parts = summary.split(' - ', 1)
    if parts:
        return parts[0].strip()
    return ""


def create_ical_from_events(events: list, calendar_name: str, dt: str = "") -> bytes:
    """Create iCal calendar from Google Calendar events.
    
    Args:
        events: List of Google Calendar events
        calendar_name: Name for the calendar
        dt: DT identifier (optional)
        
    Returns:
        iCal data as bytes
    """
    cal = Calendar()
    cal.add('prodid', '-//CLEF//Reservations//FR')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', calendar_name)
    cal.add('x-wr-timezone', 'Europe/Paris')
    
    for gcal_event in events:
        event = Event()
        
        # Generate unique UID
        event_id = gcal_event.get('id', 'unknown')
        uid = f"{dt}-res-{event_id}@clef.croix-rouge.fr" if dt else f"res-{event_id}@clef.croix-rouge.fr"
        event.add('uid', uid)
        
        # Add timestamps
        event.add('dtstamp', datetime.now(timezone.utc))
        
        # Parse and add start/end times
        start_dt = parse_event_datetime(gcal_event.get('start', {}))
        end_dt = parse_event_datetime(gcal_event.get('end', {}))
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        
        # Add summary (title)
        summary = gcal_event.get('summary', 'Réservation')
        event.add('summary', summary)
        
        # Add description
        description = gcal_event.get('description', '')
        if description:
            event.add('description', description)
        
        # Add location if available (could be extracted from description)
        # For now, we don't have a separate location field
        
        # Set status
        status = gcal_event.get('status', 'confirmed').upper()
        event.add('status', status)
        
        cal.add_component(event)
    
    return cal.to_ical()


@router.get("/{dt}/reservations.ics")
async def get_reservations_ical(
    dt: str,
    calendar_service_cache: tuple = Depends(get_calendar_service_with_cache)
) -> Response:
    """Generate iCal feed for all reservations of a DT.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        
    Returns:
        iCal file (.ics) with all reservations
    """
    calendar_service, cache = calendar_service_cache
    
    # Check cache first (1 minute TTL)
    cache_key = f"ical:{dt}:all"
    if cache and cache._connected:
        try:
            cached_ical = await cache.get(cache_key)
            if cached_ical:
                logger.info(f"Returning cached iCal for {dt}")
                return Response(
                    content=cached_ical,
                    media_type="text/calendar; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename={dt}-reservations.ics",
                        "Cache-Control": "public, max-age=60"
                    }
                )
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
    
    try:
        # Get all events from calendar
        events = calendar_service.get_events(max_results=1000)
        
        # Create iCal
        calendar_name = f"CLEF - Réservations {dt}"
        ical_data = create_ical_from_events(events, calendar_name, dt)
        
        # Cache the result for 1 minute
        if cache and cache._connected:
            try:
                await cache.set(cache_key, ical_data, ttl=60)
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
        
        return Response(
            content=ical_data,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={dt}-reservations.ics",
                "Cache-Control": "public, max-age=60"
            }
        )
    except Exception as e:
        logger.error(f"Error generating iCal for {dt}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate iCal: {str(e)}")


@router.get("/{dt}/vehicle/{immat}.ics")
async def get_vehicle_ical(
    dt: str,
    immat: str,
    calendar_service_cache: tuple = Depends(get_calendar_service_with_cache)
) -> Response:
    """Generate iCal feed for a specific vehicle's reservations.

    Args:
        dt: DT identifier (e.g., "DT75")
        immat: Vehicle license plate or indicatif

    Returns:
        iCal file (.ics) with vehicle-specific reservations
    """
    calendar_service, cache = calendar_service_cache

    # Normalize immat for comparison (remove spaces, uppercase)
    immat_normalized = immat.replace(' ', '').replace('-', '').upper()

    # Check cache first (1 minute TTL)
    cache_key = f"ical:{dt}:vehicle:{immat_normalized}"
    if cache and cache._connected:
        try:
            cached_ical = await cache.get(cache_key)
            if cached_ical:
                logger.info(f"Returning cached iCal for {dt} vehicle {immat}")
                return Response(
                    content=cached_ical,
                    media_type="text/calendar; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename={dt}-{immat}.ics",
                        "Cache-Control": "public, max-age=60"
                    }
                )
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

    try:
        # Get all events from calendar
        all_events = calendar_service.get_events(max_results=1000)

        # Filter events for this vehicle
        # Events have format: {indicatif} - {chauffeur} - {mission}
        vehicle_events = []
        for event in all_events:
            summary = event.get('summary', '')
            indicatif = extract_indicatif_from_summary(summary)

            # Normalize indicatif for comparison
            indicatif_normalized = indicatif.replace(' ', '').replace('-', '').upper()

            # Check if this event is for the requested vehicle
            if indicatif_normalized == immat_normalized or immat.upper() in summary.upper():
                vehicle_events.append(event)

        # Create iCal
        calendar_name = f"CLEF - Réservations {dt} - {immat}"
        ical_data = create_ical_from_events(vehicle_events, calendar_name, dt)

        # Cache the result for 1 minute
        if cache and cache._connected:
            try:
                await cache.set(cache_key, ical_data, ttl=60)
            except Exception as e:
                logger.warning(f"Cache write error: {e}")

        return Response(
            content=ical_data,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={dt}-{immat}.ics",
                "Cache-Control": "public, max-age=60"
            }
        )
    except Exception as e:
        logger.error(f"Error generating iCal for {dt} vehicle {immat}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate iCal: {str(e)}")

