import asyncio

class SharedState:
    def __init__(self):
        # Maps chat_id -> { "label": str, "event": asyncio.Event, "answer": str }
        self.active_questions = {}

    async def ask_user(self, chat_id, label):
        """
        Registers a question and waits for the bot to resolve it.
        """
        event = asyncio.Event()
        self.active_questions[chat_id] = {
            "label": label,
            "event": event,
            "answer": None
        }
        
        # Wait for the bot to set the event
        await event.wait()
        
        answer = self.active_questions[chat_id]["answer"]
        # Clean up
        del self.active_questions[chat_id]
        return answer

    def resolve_question(self, chat_id, answer):
        """
        Called by the bot when a user sends a text message.
        """
        if chat_id in self.active_questions:
            self.active_questions[chat_id]["answer"] = answer
            self.active_questions[chat_id]["event"].set()
            return True
        return False

    def is_waiting(self, chat_id):
        return chat_id in self.active_questions

    def get_pending_label(self, chat_id):
        return self.active_questions.get(chat_id, {}).get("label")

shared_state = SharedState()
