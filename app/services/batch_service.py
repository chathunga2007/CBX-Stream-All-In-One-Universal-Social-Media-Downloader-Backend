"""Concurrent batch and playlist media analyzer with bounded concurrency."""

import asyncio
from typing import List

from app.core.config import settings
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    BatchAnalyzeItemResult,
)
from app.services.extractor_service import extractor_service

logger = get_logger(__name__)


class BatchService:
    """Manages concurrent analysis of multiple media links and playlists."""

    def __init__(self) -> None:
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)

    async def _analyze_single_with_semaphore(self, url: str) -> BatchAnalyzeItemResult:
        """Analyze a single URL wrapped with bounded concurrency semaphore."""
        async with self.semaphore:
            try:
                data = await extractor_service.analyze_url(url)
                return BatchAnalyzeItemResult(
                    url=url,
                    success=True,
                    data=data,
                    error=None,
                )
            except Exception as e:
                logger.warning(f"Batch item failed for {url}: {e}")
                return BatchAnalyzeItemResult(
                    url=url,
                    success=False,
                    data=None,
                    error=str(e),
                )

    async def analyze_batch(self, request: BatchAnalyzeRequest) -> BatchAnalyzeResponse:
        """Concurrently analyze a batch of URLs and aggregate results."""
        urls = list(dict.fromkeys(request.urls))  # deduplicate preserving order
        tasks = [self._analyze_single_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return BatchAnalyzeResponse(
            total=len(urls),
            successful=successful,
            failed=failed,
            items=results,
        )


# Singleton batch service
batch_service = BatchService()
