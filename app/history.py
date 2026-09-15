from .extensions import db
from .models import TicketEvent


def record_event(ticket, actor, message):
    event = TicketEvent(ticket_id=ticket.id, actor_id=actor.id, message=message)
    db.session.add(event)
    db.session.commit()
