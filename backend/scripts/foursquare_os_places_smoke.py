import os
from pathlib import Path

from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog

load_dotenv(Path(__file__).parent.parent / ".env")

# Avoid AWS IMDS lookups in object store access
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["AWS_SDK_LOAD_CONFIG"] = "1"

# Default region for public bucket access
fsq_region = (
    os.getenv("FSQ_AWS_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "us-east-1"
)
os.environ.setdefault("AWS_REGION", fsq_region)
os.environ.setdefault("AWS_DEFAULT_REGION", fsq_region)

token = os.getenv("FOURSQUARE_API_KEY")
if not token:
    raise ValueError("FOURSQUARE_API_KEY is required in the environment or .env")

catalog = load_catalog(
    "default",
    **{
        "warehouse": "places",
        "uri": "https://catalog.h3-hub.foursquare.com/iceberg",
        "token": token,
        "header.content-type": "application/vnd.api+json",
        "rest-metrics-reporting-enabled": "false",
    },
)

# Small sample via PyIceberg scan
table = catalog.load_table(("datasets", "places_os"))
scan = table.scan(limit=50).select(
    *["fsq_place_id", "name", "latitude", "longitude", "locality", "region", "country"]
)
rows = scan.to_arrow().to_pylist()
print(rows[:10])
