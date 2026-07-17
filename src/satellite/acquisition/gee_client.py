"""
Google Earth Engine client initialization and authentication.
"""
import logging
import ee

logger = logging.getLogger("afrimine.satellite.gee")


def initialize_ee(project_id: str = None, service_account: str = None,
                  credentials_path: str = None) -> bool:
    """
    Initialize Google Earth Engine.

    Supports:
    - Interactive auth (default, for local dev)
    - Service account auth (for production)
    """
    try:
        if service_account and credentials_path:
            credentials = ee.ServiceAccountCredentials(
                service_account, credentials_path
            )
            ee.Initialize(credentials, project=project_id)
        else:
            try:
                ee.Initialize(project=project_id)
            except Exception:
                logger.info("Requesting Earth Engine authentication...")
                ee.Authenticate()
                ee.Initialize(project=project_id)

        # Quick validation
        logger.info(f"Earth Engine initialized. API version: {ee.__version__}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Earth Engine: {e}")
        logger.info(
            "To authenticate: run 'earthengine authenticate' in terminal, "
            "or provide service account credentials."
        )
        return False


def verify_connection() -> bool:
    """Verify GEE connection by making a simple request."""
    try:
        info = ee.Number(42).getInfo()
        logger.info(f"GEE connection verified (test value: {info})")
        return True
    except Exception as e:
        logger.error(f"GEE connection failed: {e}")
        return False
