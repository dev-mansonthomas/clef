"""Tests for Calendar service."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

os.environ["USE_MOCKS"] = "true"

from app.services.calendar_service import CalendarService


class TestCalendarService:
    def setup_method(self):
        self.service = CalendarService()
        self.service.use_mocks = True

    @pytest.mark.asyncio
    async def test_create_calendar_mock(self):
        result = await self.service.create_calendar(
            dt_id="DT75",
            name="Réservations Véhicules DT75",
            description="Calendrier des réservations",
        )

        assert "id" in result
        assert result["summary"] == "Réservations Véhicules DT75"
        assert result["description"] == "Calendrier des réservations"
        assert result["timeZone"] == "Europe/Paris"

    @pytest.mark.asyncio
    async def test_create_event_mock(self):
        start = datetime.now()
        end = start + timedelta(hours=2)

        result = await self.service.create_event(
            dt_id="DT75",
            calendar_id="mock-calendar@group.calendar.google.com",
            summary="Réservation VL-001",
            start=start,
            end=end,
            description="Réservation par Jean Dupont",
        )

        assert "id" in result
        assert result["summary"] == "Réservation VL-001"
        assert "htmlLink" in result

    @pytest.mark.asyncio
    async def test_update_event_mock(self):
        result = await self.service.update_event(
            dt_id="DT75",
            calendar_id="mock-calendar@group.calendar.google.com",
            event_id="mock-event-123",
            updates={"summary": "Updated Reservation"},
        )

        assert result["id"] == "mock-event-123"
        assert result["updated"] == True
        assert result["summary"] == "Updated Reservation"

    @pytest.mark.asyncio
    async def test_delete_event_mock(self):
        result = await self.service.delete_event(
            dt_id="DT75",
            calendar_id="mock-calendar@group.calendar.google.com",
            event_id="mock-event-123",
        )

        assert result == True

    @pytest.mark.asyncio
    async def test_list_events_mock(self):
        result = await self.service.list_events(
            dt_id="DT75",
            calendar_id="mock-calendar@group.calendar.google.com",
        )

        assert isinstance(result, list)
        assert len(result) == 0  # Mock returns empty list

