# Clef Backend

FastAPI backend for the Clef project.

## Requirements

- Python 3.13+

## Installation

```bash
# Install dependencies
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000)

## API Documentation

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI application
├── pyproject.toml       # Project dependencies
└── README.md
```