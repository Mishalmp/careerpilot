from typing import Annotated

from fastapi import Depends, Request

from careerpilot.modules.profile.cvfile import OcrFactory


def get_ocr(request: Request) -> OcrFactory:
    """Starts the OCR engine when a scanned CV needs it (None when the optional extra is absent)."""
    return request.app.state.ocr


AppOcr = Annotated[OcrFactory, Depends(get_ocr)]
