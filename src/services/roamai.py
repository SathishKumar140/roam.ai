import asyncio
import base64
import logging
import re
import time
from contextlib import suppress

from src.agents.listener import participation
from src.models.channel import ChannelEvent, OutboundMessage
from src.models.roamai import Observation


logger = logging.getLogger("roamai.listener")


class RoamAIService:
    def __init__(self, store, listener, planner, adapters=None, mode="shadow", cooldown=300, debounce=10):
        self.store = store
        self.listener = listener
        self.planner = planner
        self.adapters = adapters or {}
        self.mode = mode
        self.cooldown = cooldown
        self.debounce = debounce
        self.stop_event = asyncio.Event()
        self.tasks = []

    def enqueue(self, event):
        return self.store.enqueue(event, debounce=self.debounce)

    def _callback(self, event):
        if not event.callback_data or not event.callback_data.startswith("roamai:"):
            return None
        parts = event.callback_data.split(":")
        group_id = event.conversation_id
        try:
            if len(parts) == 4 and parts[1] == "vote":
                accepted = self.store.vote(group_id, parts[2], event.sender.id, int(parts[3]))
                return {"text": "Your vote is recorded." if accepted else "That poll is closed or unavailable."}
            if len(parts) == 4 and parts[1] == "expense" and parts[3] in {"yes", "no"}:
                state = self.store.confirm_expense(group_id, parts[2], event.sender.id, parts[3] == "yes")
                messages = {"confirmed": "Everyone confirmed this expense; it is now active.",
                            "pending": "Your confirmation is recorded. Other participants still need to confirm.",
                            "rejected": "The split was rejected. No debt has been finalized."}
                return {"text": messages.get(state, "That expense is not awaiting your confirmation.")}
        except ValueError:
            return {"text": "That action is invalid or expired."}
        return None

    async def process_once(self):
        rows = self.store.claim()
        if not rows:
            return False
        event = ChannelEvent.model_validate_json(rows[-1]["payload"])
        group_id = event.conversation_id
        try:
            async with asyncio.timeout(140):
                if event.media and event.explicitly_addressed:
                    adapter = self.adapters.get(event.platform)
                    if event.media.type in {"voice", "photo"} and adapter and hasattr(adapter, "media_bytes"):
                        try:
                            content, mime = await adapter.media_bytes(event.media)
                            if event.media.type == "voice":
                                from src.services.transcription import transcribe_audio_async
                                text = await transcribe_audio_async(content, mime_type=mime)
                                if not text:
                                    raise ValueError("Transcription unavailable")
                                event.text = text
                                with self.store.connect() as connection:
                                    connection.execute("UPDATE roamai_inbox SET payload = ? WHERE id = ? AND group_id = ?", (event.model_dump_json(), rows[-1]["id"], group_id))
                            elif mime in {"image/jpeg", "image/png", "image/webp"}:
                                event.media.url = f"data:{mime};base64," + base64.b64encode(content).decode()
                            else:
                                raise ValueError("Unsupported photo format")
                        except Exception:
                            self.store.complete(rows, response={"text": "I couldn't read that attachment. Please send a smaller image or describe it in text.", "reply_to_message_id": event.message_id})
                            return True
                    elif event.media.type in {"voice", "photo"}:
                        self.store.complete(rows, response={"text": "I can't read attachments on this connection yet. Could you describe it in text?"})
                        return True
                callback = self._callback(event)
                if callback:
                    self.store.complete(rows, response=callback | {"reply_to_message_id": event.message_id})
                    return True
                context = self.store.context(group_id, rows[-1]["id"])
                batch_ids = {str(row["id"]) for row in rows}
                batch = [message for message in context["messages"] if message["id"] in batch_ids]
                forced_topic = None
                if event.callback_data:
                    parts = event.callback_data.split(":")
                    if len(parts) == 3 and parts[1] in {"accept", "decline"} and parts[0] == "roamai":
                        accepted = self.store.accept_offer(group_id, parts[2], event.sender.id, parts[1] == "accept")
                        if not accepted or parts[1] == "decline":
                            self.store.complete(rows, response={"text": "No problem; I'll leave that with you." if accepted else "That offer is unavailable or was addressed to another member."})
                            return True
                        forced_topic = parts[2]
                        context = self.store.context(group_id, rows[-1]["id"])
                    else:
                        self.store.complete(rows, response={"text": "That action is invalid or expired."})
                        return True
                if self.store.pending_reply(group_id, event.sender.id, rows[-1]["id"]):
                    self.store.mark_responding(rows)
                observation = await asyncio.wait_for(self.listener.observe(context, batch), timeout=30)
                messages = {message["id"]: message for message in context["messages"]}
                if not set(observation.evidence_message_ids) <= messages.keys():
                    logger.warning("Observer validation failed: unknown evidence ID")
                    raise ValueError("Observer cited unknown evidence")
                known_topics = {topic["id"]: topic for topic in context["topics"]}
                comparison_ids = list(dict.fromkeys(observation.comparison_topic_ids))
                comparing = bool(event.explicitly_addressed and len(comparison_ids) >= 2
                    and set(comparison_ids) <= known_topics.keys()
                    and re.search(r"\b(?:compare|comparison|side[- ]by[- ]side)\b", event.text or "", re.I))
                if comparing:
                    observation = observation.model_copy(update={"topic_id": None, "facts": [], "preferences": [],
                        "evidence_message_ids": sorted(batch_ids)})
                if observation.topic_id and observation.topic_id not in known_topics:
                    logger.warning("Observer validation failed: unknown topic ID")
                    raise ValueError("Observer selected an unknown topic")
                if forced_topic:
                    observation = observation.model_copy(update={"topic_id": forced_topic, "decision": "respond"})
                elif event.reply_to_message_id:
                    referenced = [item for item in context["outbound"] if event.reply_to_message_id in item["provider_ids"] and item["topic_id"] in known_topics]
                    if referenced:
                        observation = observation.model_copy(update={"topic_id": referenced[0]["topic_id"]})
                if observation.clarification_question and not forced_topic:
                    response = None
                    if participation(observation, event, context, cooldown=self.cooldown) == "respond":
                        response = {"text": observation.clarification_question, "addressed_to": event.sender.id,
                                    "reply_to_message_id": event.message_id}
                    self.store.complete(rows, topic_id=observation.topic_id, response=response)
                    return True
                decision = participation(observation, event, context, cooldown=self.cooldown)
                logger.info("Observation group=%s intent=%s decision=%s mode=%s", group_id, observation.intent, decision, self.mode)
                if decision == "silent" and observation.intent == "social":
                    self.store.complete(rows)
                    return True
                members = {member["user_id"] for member in context["members"]}
                participants = sorted(set(observation.participant_ids) & members | {event.sender.id})
                observation = observation.model_copy(update={"facts": [fact for fact in observation.facts if fact.evidence_message_id in batch_ids]})
                topic_id = self.store.save_topic(group_id, rows[-1]["id"], observation, participants)
                for preference in observation.preferences:
                    source = messages.get(preference.evidence_message_id)
                    if source and source["id"] in batch_ids:
                        self.store.save_preference(group_id, source["sender_id"], preference.key, preference.value,
                            source["id"], topic_id, preference.scope, preference.evidence_quote)
                if decision == "decline":
                    self.store.set_topic_state(group_id, topic_id, "declined")
                    self.store.complete(rows)
                elif decision == "offer" and self.mode == "live":
                    candidates = [message for message in batch if message["id"] in observation.evidence_message_ids]
                    source = next((message for message in candidates if message["id"] == observation.offer_evidence_message_id), None)
                    if source is None and len({message["sender_id"] for message in candidates}) == 1:
                        source = candidates[0]
                    if source is None:
                        self.store.complete(rows)
                        return True
                    self.store.complete(rows, topic_id, {"text": observation.offer, "offered_to": source["sender_id"],
                        "reply_to_message_id": source["message_id"], "buttons": [[
                            {"id": f"roamai:accept:{topic_id}", "label": "Yes, help us"},
                            {"id": f"roamai:decline:{topic_id}", "label": "No thanks"},
                        ]]}, kind="offer")
                elif decision == "respond":
                    self.store.mark_responding(rows)
                    self.store.set_topic_state(group_id, topic_id, "active")
                    scoped_context = self.store.topic_context(group_id, topic_id, rows[-1]["id"])
                    if comparing:
                        scoped_context["comparison_topics"] = [known_topics[identity] for identity in comparison_ids]
                        scoped_context["read_only"] = True
                    topic = scoped_context["topics"][0]
                    result = await self.planner.respond(self.store, event, topic, scoped_context, str(rows[-1]["id"]))
                    self.store.complete(rows, topic_id, result | {"addressed_to": event.sender.id})
                else:
                    self.store.complete(rows)
        except Exception as error:
            logger.warning("Processing failed group=%s error=%s", group_id, type(error).__name__)
            self.store.retry(rows, type(error).__name__)
        return True

    async def deliver_once(self):
        delivery = self.store.next_delivery()
        if not delivery:
            return False
        if delivery["platform"] == "mock":
            self.store.delivery_result(delivery, True, provider_ids=[delivery["id"]])
            return True
        adapter = self.adapters.get(delivery["platform"])
        if not adapter:
            self.store.delivery_result(delivery, False, permanent=True, error="No channel adapter configured")
            return True
        try:
            message = OutboundMessage(platform=delivery["platform"], channel_id=delivery["channel_id"], **{
                key: value for key, value in delivery["payload"].items() if key in {"text", "buttons", "reply_to_message_id"}
            })
            result = await asyncio.wait_for(adapter.deliver(message), timeout=25)
            self.store.delivery_result(delivery, **result.model_dump())
            if not result.success:
                logger.warning("Delivery failed id=%s permanent=%s error=%s", delivery["id"], result.permanent, result.error)
        except Exception as error:
            self.store.delivery_result(delivery, False, error=type(error).__name__)
            logger.warning("Delivery uncertain id=%s error=%s", delivery["id"], type(error).__name__)
        return True

    async def _loop(self, operation):
        while not self.stop_event.is_set():
            try:
                await operation()
            except Exception as error:
                logger.error("Worker error=%s", type(error).__name__)
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.stop_event.wait(), timeout=0.5)

    async def _timers(self):
        self.store.close_due_polls()
        self.store.release_due_reminders()

    def start(self):
        self.stop_event.clear()
        self.tasks = [asyncio.create_task(self._loop(operation)) for operation in
                      [self.process_once, self.process_once, self.deliver_once, self._timers]]

    def readiness(self):
        from src.config import settings
        workers_running = len(self.tasks) == 4 and all(not task.done() for task in self.tasks)
        configured = bool(
            settings.GEMINI_API_KEY and (settings.DEFAULT_LLM_PROVIDER == "gemini" or not settings.OPENAI_API_KEY)
            or settings.OPENAI_API_KEY and (settings.DEFAULT_LLM_PROVIDER == "openai" or not settings.GEMINI_API_KEY)
        )
        fake_model = any("fake" in type(getattr(component, "model", None)).__name__.lower() for component in (self.listener, self.planner))
        try:
            queues = self.store.queue_status()
            database_ready = True
        except Exception:
            queues = {}
            database_ready = False
        ready = workers_running and configured and not fake_model and database_ready and queues.get("overdue", 0) == 0
        return {"ready": ready, "checks": {"workers": workers_running, "database": database_ready,
            "model_configured": configured and not fake_model, "queues_timely": database_ready and queues.get("overdue", 0) == 0},
            "provider_connectivity": "not_probed", "queues": queues}

    async def stop(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        import sys
        client = sys.modules.get("src.mcp.client")
        if client:
            for connection in client.mcp_manager.connections.values():
                connection.close()