from typing import Annotated

from fastapi import Depends, Request

from careerpilot.core.llm import LlmClient
from careerpilot.modules.knowledge.embeddings import Embedder


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_llm(request: Request) -> LlmClient | None:
    return request.app.state.llm


AppEmbedder = Annotated[Embedder, Depends(get_embedder)]
AppLlm = Annotated[LlmClient | None, Depends(get_llm)]
