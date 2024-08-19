import dotenv, os

from app import create_app  # Import the create_app function
from app.logger import log_requests, http_exception_handler, validation_exception_handler, generic_exception_handler, StarletteHTTPException, RequestValidationError


load_envar = dotenv.load_dotenv()
assert os.getenv("DEFAULT_USERNAME"), "Missing environment variables at .env"

app = create_app()
# Register middleware and exception handlers
app.middleware("http")(log_requests)
app.add_exception_handler(
  StarletteHTTPException, http_exception_handler)
app.add_exception_handler(
  RequestValidationError, validation_exception_handler)
app.add_exception_handler(
  Exception, generic_exception_handler)

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=42110)