import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models
import schemas
import feedback_message_broker as message_broker
import utility

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["FeedbackService"])

def _on_booking_created(msg: schemas.BrokerMessage) -> None:
    logger.info(
        "FeedbackService received: booking_id=%d user_id=%d at %s – '%s'",
        msg.booking_id, msg.user_id, msg.issue_date_time_utc.isoformat(), msg.message,
    )


message_broker.subscribe(_on_booking_created)


@router.post("/feedback", response_model=schemas.FeedbackResponse, status_code=201)
def create_feedback(payload: schemas.FeedbackCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check event exists via EventService
    resp = utility.get(f"{utility.EVENT_SERVICE_URL}/api/event/{payload.event_id}")
    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check user has booking via BookingService — query local DB directly (shared DB)
    booking = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.event_id == payload.event_id,
    ).first()
    if not booking:
        raise HTTPException(status_code=403, detail="You can only leave feedback for events you have booked")

    feedback = models.Feedback(event_id=payload.event_id, user_id=current_user.id, message=payload.message)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/feedback/event/{event_id}", response_model=List[schemas.FeedbackResponse])
def list_feedback(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return db.query(models.Feedback).filter(models.Feedback.event_id == event_id).all()


@router.patch("/feedback/{feedback_id}", response_model=schemas.FeedbackResponse)
def update_feedback(feedback_id: int, payload: schemas.FeedbackUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    feedback = db.query(models.Feedback).filter(
        models.Feedback.id == feedback_id,
        models.Feedback.user_id == current_user.id,
    ).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found or does not belong to you")
    if payload.message is not None:
        feedback.message = payload.message
    db.commit()
    db.refresh(feedback)
    return feedback
