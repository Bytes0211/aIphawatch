#!/usr/bin/env bash
set -euo pipefail

# Validate that all AWS resources for AIphaWatch have been deleted
# Checks both staging and production environments

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="alphawatch"
ENVIRONMENTS=("staging" "production")

resource_found=0
resource_deleted=0

log_header() {
  echo -e "\n${YELLOW}=== $1 ===${NC}\n"
}

check_resource() {
  local resource_type=$1
  local resource_name=$2
  local check_command=$3
  
  if eval "$check_command" > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} $resource_type: $resource_name EXISTS (should be deleted)"
    ((resource_found++))
  else
    echo -e "${GREEN}✓${NC} $resource_type: $resource_name deleted"
    ((resource_deleted++))
  fi
}

# ============================================================================
# VPC & Networking Resources
# ============================================================================
log_header "VPC & Networking Resources"

for env in "${ENVIRONMENTS[@]}"; do
  vpc_name="${PROJECT_NAME}-${env}-vpc"
  check_resource "VPC" "$vpc_name" \
    "aws ec2 describe-vpcs --region $AWS_REGION --filters Name=tag:Name,Values=$vpc_name --query 'Vpcs[0].VpcId' --output text | grep -q vpc-"
done

# Check Security Groups
check_resource "Security Groups" "ALB SG" \
  "aws ec2 describe-security-groups --region $AWS_REGION --filters Name=tag:Name,Values=$PROJECT_NAME-*-alb-sg --query 'SecurityGroups[0].GroupId' --output text | grep -q sg-"

check_resource "Security Groups" "RDS SG" \
  "aws ec2 describe-security-groups --region $AWS_REGION --filters Name=tag:Name,Values=$PROJECT_NAME-*-rds-sg --query 'SecurityGroups[0].GroupId' --output text | grep -q sg-"

check_resource "Security Groups" "Redis SG" \
  "aws ec2 describe-security-groups --region $AWS_REGION --filters Name=tag:Name,Values=$PROJECT_NAME-*-redis-sg --query 'SecurityGroups[0].GroupId' --output text | grep -q sg-"

# Check NAT Gateways
check_resource "NAT Gateway" "NAT allocation" \
  "aws ec2 describe-nat-gateways --region $AWS_REGION --filter Name=tag:Project,Values=$PROJECT_NAME --query 'NatGateways[0].NatGatewayId' --output text | grep -q nat-"

# ============================================================================
# Database Resources
# ============================================================================
log_header "Database Resources (RDS)"

for env in "${ENVIRONMENTS[@]}"; do
  rds_id="${PROJECT_NAME}-${env}-db"
  check_resource "RDS Instance" "$rds_id" \
    "aws rds describe-db-instances --region $AWS_REGION --db-instance-identifier $rds_id --query 'DBInstances[0].DBInstanceIdentifier' --output text | grep -q $rds_id"
done

# Check RDS Snapshots (should cleanup manually)
echo "Checking for RDS snapshots (manual cleanup may be needed)..."
SNAPSHOT_COUNT=$(aws rds describe-db-snapshots --region $AWS_REGION --query "DBSnapshots[?contains(DBSnapshotIdentifier, '$PROJECT_NAME')] | length(@)" --output text)
if [ "$SNAPSHOT_COUNT" -gt 0 ]; then
  echo -e "${YELLOW}⚠${NC}  RDS Snapshots: $SNAPSHOT_COUNT found (consider manual cleanup)"
else
  echo -e "${GREEN}✓${NC}  RDS Snapshots: none found"
fi

# ============================================================================
# Cache Resources
# ============================================================================
log_header "Cache Resources (ElastiCache)"

for env in "${ENVIRONMENTS[@]}"; do
  redis_id="${PROJECT_NAME}-${env}-redis"
  check_resource "ElastiCache Cluster" "$redis_id" \
    "aws elasticache describe-replication-groups --region $AWS_REGION --replication-group-id $redis_id --query 'ReplicationGroups[0].ReplicationGroupId' --output text | grep -q $redis_id"
done

# ============================================================================
# Container & Compute Resources
# ============================================================================
log_header "Container & Compute Resources (ECS)"

for env in "${ENVIRONMENTS[@]}"; do
  cluster_name="${PROJECT_NAME}-${env}-cluster"
  check_resource "ECS Cluster" "$cluster_name" \
    "aws ecs describe-clusters --region $AWS_REGION --clusters $cluster_name --query 'clusters[0].clusterName' --output text | grep -q $cluster_name"
done

# Check ALB
echo "Checking Application Load Balancer..."
ALB_COUNT=$(aws elbv2 describe-load-balancers --region $AWS_REGION --query "LoadBalancers[?contains(LoadBalancerName, '$PROJECT_NAME')] | length(@)" --output text)
if [ "$ALB_COUNT" -gt 0 ]; then
  echo -e "${RED}✗${NC} ALB: $ALB_COUNT found (should be deleted)"
  ((resource_found++))
else
  echo -e "${GREEN}✓${NC} ALB: none found"
  ((resource_deleted++))
fi

# Check Target Groups
echo "Checking Target Groups..."
TG_COUNT=$(aws elbv2 describe-target-groups --region $AWS_REGION --query "TargetGroups[?contains(TargetGroupName, '$PROJECT_NAME')] | length(@)" --output text)
if [ "$TG_COUNT" -gt 0 ]; then
  echo -e "${RED}✗${NC} Target Groups: $TG_COUNT found (should be deleted)"
  ((resource_found++))
else
  echo -e "${GREEN}✓${NC} Target Groups: none found"
  ((resource_deleted++))
fi

# ============================================================================
# Storage Resources
# ============================================================================
log_header "Storage Resources (S3)"

for env in "${ENVIRONMENTS[@]}"; do
  bucket_prefix="${PROJECT_NAME}-${env}"
  echo "Checking S3 buckets with prefix: $bucket_prefix"
  BUCKET_COUNT=$(aws s3api list-buckets --region $AWS_REGION --query "Buckets[?contains(Name, '$bucket_prefix')] | length(@)" --output text)
  if [ "$BUCKET_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC}  S3 Buckets: $BUCKET_COUNT found (verify if should be deleted)"
    ((resource_found++))
  else
    echo -e "${GREEN}✓${NC}  S3 Buckets: none found"
    ((resource_deleted++))
  fi
done

# ============================================================================
# Authentication Resources
# ============================================================================
log_header "Authentication Resources (Cognito)"

for env in "${ENVIRONMENTS[@]}"; do
  pool_name="${PROJECT_NAME}-${env}-pool"
  echo "Checking Cognito User Pool: $pool_name"
  POOL_COUNT=$(aws cognito-idp list-user-pools --region $AWS_REGION --max-results 60 --query "UserPools[?contains(Name, '$env')] | length(@)" --output text)
  if [ "$POOL_COUNT" -gt 0 ]; then
    echo -e "${RED}✗${NC} Cognito User Pool: $POOL_COUNT found (should be deleted)"
    ((resource_found++))
  else
    echo -e "${GREEN}✓${NC} Cognito User Pool: none found"
    ((resource_deleted++))
  fi
done

# ============================================================================
# CDN Resources
# ============================================================================
log_header "CDN Resources (CloudFront)"

echo "Checking CloudFront distributions..."
CF_COUNT=$(aws cloudfront list-distributions --region $AWS_REGION --query "DistributionList.Items[?contains(Comment, '$PROJECT_NAME')] | length(@)" --output text)
if [ "$CF_COUNT" -gt 0 ]; then
  echo -e "${RED}✗${NC} CloudFront Distributions: $CF_COUNT found (should be deleted)"
  ((resource_found++))
else
  echo -e "${GREEN}✓${NC} CloudFront Distributions: none found"
  ((resource_deleted++))
fi

# ============================================================================
# Secrets & Configuration
# ============================================================================
log_header "Secrets & Configuration (Secrets Manager)"

for env in "${ENVIRONMENTS[@]}"; do
  check_resource "Secrets" "${PROJECT_NAME}/${env}/*" \
    "aws secretsmanager list-secrets --region $AWS_REGION --filters Key=name,Values=${PROJECT_NAME}/${env}/ --query 'SecretList[0].Name' --output text | grep -q /"
done

# ============================================================================
# Build & Pipeline Resources
# ============================================================================
log_header "Build & Pipeline Resources (CodeBuild)"

for env in "${ENVIRONMENTS[@]}"; do
  project_name="${PROJECT_NAME}-${env}-migration-drill"
  check_resource "CodeBuild Project" "$project_name" \
    "aws codebuild batch-get-projects --region $AWS_REGION --names $project_name --query 'projects[0].name' --output text | grep -q $project_name"
done

# ============================================================================
# IAM Resources
# ============================================================================
log_header "Identity & Access Management (IAM)"

# Check for service roles
for env in "${ENVIRONMENTS[@]}"; do
  role_name="${PROJECT_NAME}-${env}-api-role"
  check_resource "IAM Role" "$role_name" \
    "aws iam get-role --role-name $role_name --query 'Role.RoleName' --output text | grep -q $role_name"
done

# Check for deploy roles
check_resource "IAM Role" "GitHub Deploy Role" \
  "aws iam get-role --role-name TerraformGitHubActionsRole --query 'Role.RoleName' --output text | grep -q TerraformGitHubActionsRole"

check_resource "IAM Role" "GitHub Deploy Role (Production)" \
  "aws iam get-role --role-name TerraformGitHubActionsRoleProd --query 'Role.RoleName' --output text | grep -q TerraformGitHubActionsRoleProd"

# ============================================================================
# Summary
# ============================================================================
log_header "Cleanup Validation Summary"

echo "Resources successfully deleted: $resource_deleted"
echo "Resources still found:           $resource_found"

if [ $resource_found -eq 0 ]; then
  echo -e "\n${GREEN}✓ All AWS resources have been successfully deleted!${NC}\n"
  exit 0
else
  echo -e "\n${RED}✗ $resource_found resource(s) still exist and need cleanup${NC}\n"
  exit 1
fi
