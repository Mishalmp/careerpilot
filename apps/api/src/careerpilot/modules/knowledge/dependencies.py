from typing import Annotated

from fastapi import Depends, Request

from careerpilot.modules.knowledge.embeddings import Embedder


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


AppEmbedder = Annotated[Embedder, Depends(get_embedder)]
