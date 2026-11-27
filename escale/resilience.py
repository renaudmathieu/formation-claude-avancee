"""When the API is down, say so politely instead of crashing, and stop hammering it."""

import time

from escale.llm import RETRYABLE

DEGRADED_MESSAGE = (
    "Escale est momentanément indisponible (le service de l'IA ne répond pas). "
    "Réessayez dans quelques minutes."
)


class CircuitOpenError(Exception):
    """The breaker is open: the call was not even tried."""


class CircuitBreaker:
    """Stop calling a service that keeps failing, and try again after a pause.

    closed: calls go through. After `threshold` failures in a row it opens.
    open: calls fail at once, without waiting for a timeout, during `cooldown` seconds.
    then one call is let through: if it works the breaker closes, if not it opens again.
    """

    def __init__(self, threshold: int = 3, cooldown: float = 30.0, clock=time.monotonic):
        self.threshold = threshold
        self.cooldown = cooldown
        self.clock = clock
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        return self.opened_at is not None and self.clock() - self.opened_at < self.cooldown

    def call(self, function):
        """Run `function()` under the breaker."""
        if self.is_open:
            raise CircuitOpenError("Le disjoncteur est ouvert.")
        try:
            result = function()
        except RETRYABLE:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = self.clock()
            raise
        # Any other error (a 400, a 401) is a fault in the request, not an outage: it does not
        # count here, and a success closes the breaker.
        self.failures = 0
        self.opened_at = None
        return result
