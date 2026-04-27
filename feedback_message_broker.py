import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

import json
import logging
import threading
import time
from datetime import datetime
from typing import Callable, List
from dotenv import load_dotenv
from azure.servicebus import ServiceBusClient
from schemas import BrokerMessage

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, '.env'))

logger = logging.getLogger(__name__)

SERVICE_BUS_READ_CONN_STR = os.getenv("SERVICE_BUS_READ_CONN_STR")
QUEUE_NAME                = os.getenv("QUEUE_NAME", "aliakseibanshchyk")
POLL_INTERVAL_SECONDS     = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
print("READ CONN STR:", SERVICE_BUS_READ_CONN_STR)

_subscribers: List[Callable[[BrokerMessage], None]] = []
_lock = threading.Lock()


def subscribe(handler: Callable[[BrokerMessage], None]) -> None:
    with _lock:
        _subscribers.append(handler)
    logger.info("Broker: subscriber registered – %s", handler.__name__)


def _receive_loop() -> None:
    logger.info("Broker: receiver started (interval=%ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            with ServiceBusClient.from_connection_string(SERVICE_BUS_READ_CONN_STR) as client:
                with client.get_queue_receiver(QUEUE_NAME, max_wait_time=5) as receiver:
                    for raw in receiver:
                        try:
                            data = json.loads(str(raw))
                            msg = BrokerMessage(
                                issue_date_time_utc=datetime.fromisoformat(data["issue_date_time_utc"]),
                                user_id=data["user_id"],
                                booking_id=data["booking_id"],
                                message=data["message"],
                            )
                            with _lock:
                                handlers = list(_subscribers)
                            for handler in handlers:
                                threading.Thread(target=_safe_call, args=(handler, msg), daemon=True).start()
                            receiver.complete_message(raw)
                        except Exception as exc:
                            logger.error("Broker: bad message – %s", exc)
                            receiver.dead_letter_message(raw)
        except Exception as exc:
            logger.error("Broker: receiver error – %s", exc)
        time.sleep(POLL_INTERVAL_SECONDS)


def _safe_call(handler, msg):
    try:
        handler(msg)
    except Exception as exc:
        logger.error("Broker: handler %s raised %s", handler.__name__, exc)


def start_receiver() -> None:
    t = threading.Thread(target=_receive_loop, daemon=True)
    t.start()
    logger.info("Broker: background receiver thread started")
