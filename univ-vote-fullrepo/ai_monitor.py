from datetime import datetime, timezone
import random, logging

class AIMonitor:
    def __init__(self):
        self.vote_rate_window = []
        self.threshold = 20
    def check_incoming_vote(self, payload):
        now = datetime.now(timezone.utc).timestamp()
        self.vote_rate_window = [t for t in self.vote_rate_window if now - t < 60]
        self.vote_rate_window.append(now)
        if len(self.vote_rate_window) > self.threshold:
            logging.warning('AIMonitor: high vote rate detected: %s', len(self.vote_rate_window))
            return True
        if random.random() < 0.01:
            logging.warning('AIMonitor: simulated anomaly random trigger.')
            return True
        return False
