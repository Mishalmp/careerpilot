from fastapi import APIRouter

from careerpilot.core.deps import AppSettings
from careerpilot.modules.architecture import service
from careerpilot.modules.architecture.schemas import ConceptDetail, ConceptSummary, Diagram, Flow
from careerpilot.modules.auth.dependencies import Authenticated

router = APIRouter(prefix="/architecture", tags=["architecture"])


@router.get("/diagrams", operation_id="list_architecture_diagrams")
async def diagrams(_: Authenticated, settings: AppSettings) -> list[Diagram]:
    return service.load_diagrams(settings.content_dir)


@router.get("/flows", operation_id="list_architecture_flows")
async def flows(_: Authenticated, settings: AppSettings) -> list[Flow]:
    return service.load_flows(settings.content_dir)


@router.get("/concepts", operation_id="list_architecture_concepts")
async def concepts(_: Authenticated, settings: AppSettings) -> list[ConceptSummary]:
    return service.concept_summaries(settings.content_dir)


@router.get("/concepts/{concept_id}", operation_id="get_architecture_concept")
async def concept(concept_id: str, _: Authenticated, settings: AppSettings) -> ConceptDetail:
    return service.get_concept(settings.content_dir, concept_id)
