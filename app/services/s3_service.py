import boto3
from flask import current_app
import uuid
import os
from botocore.exceptions import ClientError, NoCredentialsError
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = None
        self.bucket_name = current_app.config.get('S3_BUCKET_NAME')
        self.region = current_app.config.get('S3_REGION', 'us-east-1')
        self.s3_available = False
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize S3 client dengan credentials"""
        try:
            # Check if S3 credentials are available
            access_key = current_app.config.get('S3_ACCESS_KEY')
            secret_key = current_app.config.get('S3_SECRET_KEY')
            
            if not access_key or not secret_key or not self.bucket_name:
                logger.warning("S3 credentials not configured. S3 uploads will be disabled.")
                self.s3_available = False
                return False
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=self.region
            )
            
            # Verify bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 client initialized successfully for bucket: {self.bucket_name} in region: {self.region}")
            self.s3_available = True
            return True
            
        except NoCredentialsError:
            logger.warning("AWS credentials not found. S3 uploads will be disabled.")
            self.s3_available = False
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.warning(f"S3 client initialization failed: {error_code} - {str(e)}. S3 uploads will be disabled.")
            self.s3_available = False
            return False
        except Exception as e:
            logger.warning(f"S3 configuration error: {str(e)}. S3 uploads will be disabled.")
            self.s3_available = False
            return False
    
    def upload_product_image(self, file, product_id=None):
        """Upload gambar produk ke S3 atau return None jika S3 tidak tersedia"""
        try:
            # If S3 is not available, return None instead of raising error
            if not self.s3_available or not self.s3_client:
                logger.info("S3 not available, skipping image upload")
                return None
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            
            if file_extension not in allowed_extensions:
                logger.warning(f"File type {file_extension} not allowed")
                return None
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            if product_id:
                s3_key = f"products/{product_id}/{unique_filename}"
            else:
                s3_key = f"products/{unique_filename}"
            
            # Upload file ke S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': file.content_type or 'image/jpeg'
                }
            )
            
            # Generate public URL
            if self.region == 'us-east-1':
                url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            else:
                url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"✅ Image uploaded successfully: {s3_key}")
            return url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"❌ S3 upload error {error_code}: {str(e)}")
            return None  # Return None instead of raising error
        except Exception as e:
            logger.error(f"❌ Image upload error: {str(e)}")
            return None  # Return None instead of raising error
    
    def check_file_public_access(self, object_name):
        """Check if a file is publicly accessible"""
        if not self.s3_available:
            return False
            
        try:
            # Try to access without credentials
            public_s3 = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
            response = public_s3.head_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            return True
        except ClientError as e:
            logger.error(f"File not publicly accessible: {str(e)}")
            return False
    
    def generate_presigned_url(self, object_name, expiration=3600):
        """Generate presigned URL untuk akses private files"""
        if not self.s3_available or not self.s3_client:
            return None
            
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name, 
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"S3 presigned URL error: {str(e)}")
            return None
    
    def delete_file(self, object_name):
        """Delete file dari S3"""
        if not self.s3_available or not self.s3_client:
            return False
            
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            logger.info(f"File deleted from S3: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {str(e)}")
            return False
    
    def list_files(self, prefix=''):
        """List files dalam S3 bucket"""
        if not self.s3_available or not self.s3_client:
            return []
            
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{obj['Key']}"
                    })
            
            return files
        except ClientError as e:
            logger.error(f"S3 list files error: {str(e)}")
            return []