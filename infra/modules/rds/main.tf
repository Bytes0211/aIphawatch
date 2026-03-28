###############################################################################
# RDS Module — AIphaWatch
# PostgreSQL 16 with pgvector extension.
###############################################################################

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-db-subnet"
  })
}

resource "aws_db_parameter_group" "postgres16" {
  name   = "${var.project}-${var.environment}-pg16"
  family = "postgres16"

  # Note: pgvector is installed via CREATE EXTENSION, not shared_preload_libraries.
  # shared_preload_libraries is reserved for pg_stat_statements, pg_cron, etc.
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_statement"
    value = var.environment == "production" ? "ddl" : "all"
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-pg16-params"
  })
}

resource "aws_db_instance" "main" {
  identifier = "${var.project}-${var.environment}-db"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class
  port           = 5432

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.postgres16.name
  publicly_accessible    = false

  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.environment == "staging"
  final_snapshot_identifier = var.environment == "staging" ? null : "${var.project}-${var.environment}-final"

  performance_insights_enabled = var.environment == "production"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-db"
  })
}
