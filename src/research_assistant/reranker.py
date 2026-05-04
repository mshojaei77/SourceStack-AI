import logging

from .config import settings

logger = logging.getLogger(__name__)


class Reranker:
    def __init__(self) -> None:
        self.model = None
        if not settings.reranker_enabled:
            return
        try:
            import torch
            from transformers import AutoConfig, AutoModel

            config = AutoConfig.from_pretrained(settings.reranker_model, trust_remote_code=True)
            if hasattr(config, "tie_word_embeddings"):
                config.tie_word_embeddings = False

            self.model = AutoModel.from_pretrained(
                settings.reranker_model,
                trust_remote_code=True,
                config=config,
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = self.model.to(device)
            self.model.eval()
            logger.info("Loaded reranker %s on %s", settings.reranker_model, device)
        except Exception as exc:
            logger.warning("Reranker unavailable, using vector order: %s", exc)
            self.model = None

    def rank(self, query: str, documents: list[str], top_k: int) -> list[dict]:
        if not self.model:
            return [{"index": index, "score": 0.0} for index in range(min(top_k, len(documents)))]

        try:
            ranked = self.model.rerank(query, documents, top_n=top_k)
            return [
                {"index": item.get("index", 0), "score": item.get("relevance_score", 0.0)}
                for item in ranked
            ]
        except Exception as exc:
            logger.warning("Reranking failed, using vector order: %s", exc)
            return [{"index": index, "score": 0.0} for index in range(min(top_k, len(documents)))]


_reranker: Reranker | None = None


def rerank(query: str, rows: list[dict], top_k: int) -> list[dict]:
    global _reranker
    if not settings.reranker_enabled or len(rows) <= 1:
        return rows[:top_k]

    if _reranker is None:
        _reranker = Reranker()

    ranked_rows: list[dict] = []
    for item in _reranker.rank(query, [row["text"] for row in rows], top_k):
        index = item["index"]
        if 0 <= index < len(rows):
            row = rows[index].copy()
            row["rerank_score"] = item["score"]
            ranked_rows.append(row)
    return ranked_rows or rows[:top_k]
