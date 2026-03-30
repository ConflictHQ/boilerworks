# boilerworks bootstrap

Run Terraform infrastructure layers. Requires a generated ops directory (from `boilerworks init` with `ops: true`).

```bash
boilerworks bootstrap
boilerworks bootstrap --dry-run
```

!!! warning "v2 feature"
    `bootstrap` is a v2 CLI feature. The ops Terraform files are fully functional — run them directly with `./run.sh` in the ops directory. The CLI wrapper is coming in v0.2.

## Manual bootstrap (v1)

Until the CLI wrapper lands, use `run.sh` directly:

```bash
cd my-app-ops          # or my-app/ops for omni topology

# Edit cloud config
vim aws/config.env     # set PROJECT, AWS_REGION

# Bootstrap state backend (S3 + DynamoDB)
./run.sh bootstrap aws dev

# Plan and apply
./run.sh plan aws dev
./run.sh apply aws dev
```

## run.sh commands

| Command | Description |
|---------|-------------|
| `./run.sh init aws dev` | `terraform init` for AWS dev |
| `./run.sh plan aws dev` | `terraform plan` |
| `./run.sh apply aws dev` | `terraform apply` |
| `./run.sh destroy aws dev` | `terraform destroy` |
| `./run.sh fmt` | Format all `.tf` files |
| `./run.sh validate` | Validate all Terraform directories |
| `./run.sh bootstrap aws dev` | Create state backend + init |

## What gets created

Running `./run.sh apply aws dev` provisions:

- VPC (3 AZs, public/private/database/cache subnets)
- ECS Fargate cluster + service
- RDS PostgreSQL 16
- ElastiCache Redis 7
- Application Load Balancer (HTTPS)
- Route53 hosted zone + A record
- ACM wildcard TLS certificate
- S3 file storage bucket
- Secrets Manager (db creds, app secrets)
- CloudWatch log groups + alarms
- IAM roles (ECS task execution, CI/CD)
- Security groups (ALB → ECS → RDS/Redis)
