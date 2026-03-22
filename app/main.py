from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.actor import resolve_current_actor, router as actor_router
from app.routes import render_template
from app.routes.entries import router as entries_router
from app.routes.home import lifespan, router as home_router
from app.routes.labels import router as labels_router
from app.routes.settings import router as settings_router
from app.routes.vendors import router as vendors_router
from app.runtime import APP_ROOT_PATH

app = FastAPI(lifespan=lifespan, root_path=APP_ROOT_PATH)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    status_code = exc.status_code
    if status_code == 404:
        response = render_template(
            request,
            "404.html",
            {"message": str(exc.detail or "The requested page could not be found.")},
        )
        response.status_code = 404
        return response

    if status_code >= 400:
        response = render_template(
            request,
            "error.html",
            {
                "status_code": status_code,
                "message": str(exc.detail or "The request could not be processed."),
            },
        )
        response.status_code = status_code
        return response

    return render_template(
        request,
        "error.html",
        {"status_code": 500, "message": "An unexpected error occurred."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, _exc: RequestValidationError):
    response = render_template(
        request,
        "error.html",
        {
            "status_code": 400,
            "message": "Some form fields were missing or invalid.",
        },
    )
    response.status_code = 400
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, _exc: Exception):
    response = render_template(
        request,
        "error.html",
        {
            "status_code": 500,
            "message": "An unexpected error occurred. Please try again.",
        },
    )
    response.status_code = 500
    return response


@app.middleware("http")
async def actor_context_middleware(request: Request, call_next):
    request.state.current_actor = resolve_current_actor(request)
    return await call_next(request)


app.include_router(home_router)
app.include_router(actor_router)
app.include_router(vendors_router)
app.include_router(entries_router)
app.include_router(labels_router)
app.include_router(settings_router)
