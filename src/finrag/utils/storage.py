import os
import structlog
from abc import ABC, abstractmethod
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from finrag.core.config import settings

logger = structlog.get_logger(__name__)

class BaseStorageClient(ABC):
    """Abstract interface for all document storage backends."""

    @abstractmethod
    async def upload_file(self, file_bytes: bytes, filename: str, bucket: str = "documents") -> str:
        """Uploads a file and returns a unique storage URI."""
        pass

    @abstractmethod
    async def download_file(self, storage_uri: str) -> bytes:
        """Downloads a file given its storage URI."""
        pass

class S3StorageClient(BaseStorageClient):
    """Storage client implementing MinIO / AWS S3 persistence using boto3."""

    def __init__(self) -> None:
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY.get_secret_value()
        self.secure = settings.MINIO_SECURE

        # Ensure endpoint has protocol
        protocol = "https" if self.secure else "http"
        endpoint_url = f"{protocol}://{self.endpoint}" if not self.endpoint.startswith("http") else self.endpoint

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1"
        )

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            self.s3.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404" or error_code == 404:
                self.s3.create_bucket(Bucket=bucket)
                logger.info("Created missing S3 bucket", bucket=bucket)
            else:
                raise

    async def upload_file(self, file_bytes: bytes, filename: str, bucket: str = "documents") -> str:
        self._ensure_bucket(bucket)
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=filename,
                Body=file_bytes
            )
            uri = f"s3://{bucket}/{filename}"
            logger.info("Successfully uploaded file to S3", uri=uri)
            return uri
        except Exception as e:
            logger.error("Failed to upload file to S3", filename=filename, error=str(e))
            raise

    async def download_file(self, storage_uri: str) -> bytes:
        if not storage_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {storage_uri}")
        parts = storage_uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {storage_uri}")
        bucket, key = parts

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception as e:
            logger.error("Failed to download file from S3", uri=storage_uri, error=str(e))
            raise

class LocalStorageClient(BaseStorageClient):
    """Fallback local filesystem storage client."""

    def __init__(self, base_dir: str = "storage") -> None:
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info("Initialized local filesystem storage fallback", base_dir=self.base_dir)

    async def upload_file(self, file_bytes: bytes, filename: str, bucket: str = "documents") -> str:
        bucket_dir = os.path.join(self.base_dir, bucket)
        os.makedirs(bucket_dir, exist_ok=True)
        file_path = os.path.join(bucket_dir, filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # Convert path to standard URI structure
        normalized_path = file_path.replace("\\", "/")
        uri = f"file:///{normalized_path}"
        logger.info("Successfully saved file locally", uri=uri)
        return uri

    async def download_file(self, storage_uri: str) -> bytes:
        if not storage_uri.startswith("file:///"):
            raise ValueError(f"Invalid local file URI: {storage_uri}")

        file_path = storage_uri[8:]
        # Normalize back for windows
        file_path = os.path.normpath(file_path)

        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error("Failed to read local file", uri=storage_uri, error=str(e))
            raise

_storage_client: BaseStorageClient | None = None

def get_storage_client() -> BaseStorageClient:
    """Singleton getter returning configured storage client (falling back to Local if S3 is unavailable)."""
    global _storage_client
    if _storage_client is not None:
        return _storage_client

    try:
        client = S3StorageClient()
        # Verify connection capability
        client.s3.list_buckets()
        _storage_client = client
        logger.info("Using S3/MinIO storage client backend")
    except Exception as e:
        logger.warning(
            "Could not connect to S3/MinIO endpoint. Falling back to local storage.",
            endpoint=settings.MINIO_ENDPOINT,
            error=str(e)
        )
        _storage_client = LocalStorageClient()

    return _storage_client
