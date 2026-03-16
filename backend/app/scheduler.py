"""Scheduler for periodic tasks like alert checking."""
import os
import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.alert_service import AlertService
from app.services.config_service import ConfigService
from app.cache import get_cache

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


async def check_alerts_job():
    """Job to check and send vehicle alerts."""
    logger.info("Running scheduled alert check")
    
    try:
        # Initialize services
        cache = get_cache()
        config_service = ConfigService(cache)
        alert_service = AlertService(config_service)
        
        # Run alert check
        result = await alert_service.check_and_send_alerts()
        
        logger.info(f"Alert check completed: {result}")
    except Exception as e:
        logger.error(f"Error in scheduled alert check: {e}", exc_info=True)


def start_scheduler():
    """Start the scheduler with configured jobs."""
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already started")
        return
    
    # Check if scheduler should be enabled
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    
    if not scheduler_enabled:
        logger.info("Scheduler disabled by configuration")
        return
    
    logger.info("Starting scheduler")
    
    # Create scheduler
    scheduler = AsyncIOScheduler()
    
    # Get cron schedule from environment (default: daily at 8:00 AM)
    cron_hour = os.getenv("ALERT_CRON_HOUR", "8")
    cron_minute = os.getenv("ALERT_CRON_MINUTE", "0")
    
    # Add alert check job
    scheduler.add_job(
        check_alerts_job,
        trigger=CronTrigger(hour=cron_hour, minute=cron_minute),
        id="check_alerts",
        name="Check vehicle alerts",
        replace_existing=True
    )
    
    logger.info(f"Scheduled alert check job to run daily at {cron_hour}:{cron_minute}")
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    
    if scheduler is None:
        logger.warning("Scheduler not running")
        return
    
    logger.info("Stopping scheduler")
    scheduler.shutdown()
    scheduler = None
    logger.info("Scheduler stopped")


def get_scheduler() -> AsyncIOScheduler:
    """
    Get the scheduler instance.
    
    Returns:
        Scheduler instance or None if not started
    """
    return scheduler

