"""Main application entry point."""

from fastapi import FastAPI

app = FastAPI(title="AI Video Studio API", version="0.0.1")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "AI Video Studio API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
