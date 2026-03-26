###############################################################################
# S3 Module — AIphaWatch
# Document storage bucket + frontend static hosting bucket.
###############################################################################

# -----------------------------------------------------------------------------
# Document Storage Bucket (private, versioned, encrypted)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "documents" {
  bucket = "${var.project}-${var.environment}-documents"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-documents"
  })
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "archive-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# -----------------------------------------------------------------------------
# Frontend Static Hosting Bucket
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project}-${var.environment}-frontend"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-frontend"
  })
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "frontend_oai" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontOAI"
      Effect    = "Allow"
      Principal = { AWS = var.cloudfront_oai_arn }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
    }]
  })
}
