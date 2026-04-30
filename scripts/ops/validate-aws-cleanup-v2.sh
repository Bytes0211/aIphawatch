#!/usr/bin/env bash
set -u

# Simplified AWS cleanup validation script with better error handling
# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="alphawatch"

resource_found=0
resource_deleted=0

echo "AWS Cleanup Validation Report"
echo "=============================="
echo "Region: $AWS_REGION"
echo "Project: $PROJECT_NAME"
echo ""

# Helper function
check_exists() {
  local name=$1
  local cmd=$2
  
  echo -n "Checking $name... "
  
  if output=$(eval "$cmd" 2>&1); then
    if echo "$output" | grep -qE "(^[a-z]{2}-|^[0-9]|\[None\]|vpc-|sg-|nat-|TruOAuth|rds-)"; then
      echo -e "${RED}FOUND${NC}"
      ((resource_found++))
      return 0
    fi
  fi
  
  echo -e "${GREEN}deleted${NC}"
  ((resource_deleted++))
  return 1
}

# ============================================================================
# VPC Resources
# ============================================================================
echo "=== VPC & Networking ==="
check_exists "Staging VPC" "aws ec2 describe-vpcs --region $AWS_REGION --filters Name=resource-id,Values=vpc-* --query 'Vpcs[?Tags[?Key==\`Project\`].Value | [0]]==\`alphawatch\`' --output text"
check_exists "Production VPC" "aws ec2 describe-vpcs --region $AWS_REGION --filters Name=tag:Project,Values=alphawatch --query 'Vpcs[0].VpcId' --output text"

# ============================================================================
# RDS Instances
# ============================================================================
echo ""
echo "=== Database (RDS) ==="
check_exists "Staging RDS" "aws rds describe-db-instances --region $AWS_REGION --query 'DBInstances[?DBInstanceIdentifier==\`alphawatch-staging-db\`].DBInstanceIdentifier' --output text"
check_exists "Production RDS" "aws rds describe-db-instances --region $AWS_REGION --query 'DBInstances[?DBInstanceIdentifier==\`alphawatch-production-db\`].DBInstanceIdentifier' --output text"

# ============================================================================
# ElastiCache/Redis
# ============================================================================
echo ""
echo "=== Cache (Redis/ElastiCache) ==="
check_exists "Staging Redis" "aws elasticache describe-replication-groups --region $AWS_REGION --query 'ReplicationGroups[?ReplicationGroupId==\`alphawatch-staging-redis\`].ReplicationGroupId' --output text"
check_exists "Production Redis" "aws elasticache describe-replication-groups --region $AWS_REGION --query 'ReplicationGroups[?ReplicationGroupId==\`alphawatch-production-redis\`].ReplicationGroupId' --output text"

# ============================================================================
# ECS Clusters
# ============================================================================
echo ""
echo "=== Container (ECS) ==="
check_exists "Staging ECS Cluster" "aws ecs describe-clusters --region $AWS_REGION --clusters alphawatch-staging-cluster --query 'clusters[0].clusterName' --output text"
check_exists "Production ECS Cluster" "aws ecs describe-clusters --region $AWS_REGION --clusters alphawatch-production-cluster --query 'clusters[0].clusterName' --output text"

# ============================================================================
# Load Balancer
# ============================================================================
echo ""
echo "=== Load Balancer ==="
check_exists "ALB" "aws elbv2 describe-load-balancers --region $AWS_REGION --query 'LoadBalancers[?contains(LoadBalancerName, \`alphawatch\`)].LoadBalancerName' --output text"

# ============================================================================
# S3 Buckets
# ============================================================================
echo ""
echo "=== Storage (S3) ==="
check_exists "S3 Buckets" "aws s3api list-buckets --query \"Buckets[?contains(Name, 'alphawatch')].Name\" --output text"

# ============================================================================
# Cognito
# ============================================================================
echo ""
echo "=== Authentication (Cognito) ==="
check_exists "Cognito Pools" "aws cognito-idp list-user-pools --region $AWS_REGION --max-results 60 --query \"UserPools[?contains(Name, 'alphawatch')].Id\" --output text"

# ============================================================================
# CloudFront
# ============================================================================
echo ""
echo "=== CDN (CloudFront) ==="
check_exists "CloudFront Distributions" "aws cloudfront list-distributions --query \"DistributionList.Items[?contains(Comment, 'alphawatch')].Id\" --output text"

# ============================================================================
# IAM Roles
# ============================================================================
echo ""
echo "=== IAM Roles ==="
check_exists "Staging API Role" "aws iam get-role --role-name alphawatch-staging-api-role --query 'Role.RoleName' --output text"
check_exists "Production API Role" "aws iam get-role --role-name alphawatch-production-api-role --query 'Role.RoleName' --output text"
check_exists "GitHub Actions Deploy Role" "aws iam get-role --role-name TerraformGitHubActionsRole --query 'Role.RoleName' --output text"
check_exists "GitHub Actions Production Role" "aws iam get-role --role-name TerraformGitHubActionsRoleProd --query 'Role.RoleName' --output text"

# ============================================================================
# Secrets Manager
# ============================================================================
echo ""
echo "=== Secrets (Secrets Manager) ==="
check_exists "Secrets" "aws secretsmanager list-secrets --region $AWS_REGION --filters Key=name,Values=alphawatch/ --query 'SecretList[0].Name' --output text"

# ============================================================================
# CodeBuild Projects
# ============================================================================
echo ""
echo "=== Build (CodeBuild) ==="
check_exists "Migration Drill Project" "aws codebuild batch-get-projects --region $AWS_REGION --names alphawatch-staging-migration-drill --query 'projects[0].name' --output text"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "=============================="
echo "Validation Summary"
echo "=============================="
echo "Resources deleted:    $((resource_deleted))"
echo "Resources remaining:  $((resource_found))"

if [ $resource_found -eq 0 ]; then
  echo -e "\n${GREEN}✓ All AWS resources have been successfully deleted!${NC}\n"
  exit 0
else
  echo -e "\n${RED}✗ $resource_found resource(s) still exist${NC}\n"
  exit 1
fi
