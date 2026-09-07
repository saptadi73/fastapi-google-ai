from fastapi import APIRouter as FastAPIRouter
from fastapi.responses import Response
from fastapi.routing import APIRoute

from app.schemas.common import Envelope


class EnvelopeRoute(APIRoute):
    def __init__(self, *args, **kwargs):
        response_class = kwargs.get("response_class")
        if not isinstance(response_class, type) or response_class is not Response:
            if kwargs.get("response_model") is None:
                kwargs["response_model"] = Envelope
        super().__init__(*args, **kwargs)


class APIRouter(FastAPIRouter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("route_class", EnvelopeRoute)
        super().__init__(*args, **kwargs)
