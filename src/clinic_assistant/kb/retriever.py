"""Full-text search over doc_chunks (ADR 0003).

Owner: @NoorAlbusaidi (#13). Shell from #83 so the graph and app can wire it: add the methods.
"""

from clinic_assistant.repository.db import DictPool


class Retriever:
    """Find the clinic passages that best match a question."""

    def __init__(self, pool: DictPool) -> None:
        self.pool = pool
