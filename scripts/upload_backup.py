import os
from pathlib import Path

import boto3

path = Path(os.environ["BACKUP_FILE"])
client = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT_URL"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)
client.upload_file(str(path), os.environ["R2_BUCKET"], f"backups/supabase/{path.name}")
