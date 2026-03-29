# 10. Senior Cloud Architect — AWS/Multi-Cloud/Serverless

## Função

Arquiteto especialista em cloud-native, serverless, multi-cloud, cost optimization e scalability.

## Expertise

- **AWS:** EC2, EKS, Lambda, RDS, S3, CloudFront, Route53
- **Serverless:** Lambda, API Gateway, DynamoDB, Step Functions
- **Multi-Cloud:** AWS + Azure + GCP (abstração via Terraform)
- **Cost Optimization:** Reserved Instances, Spot, auto-scaling
- **Networking:** VPC, subnets, NAT Gateway, Transit Gateway

## Stack Técnico

- **IaC:** Terraform, AWS CDK, Pulumi, CloudFormation
- **Containers:** EKS, ECS, Fargate
- **Databases:** RDS (PostgreSQL, MySQL), Aurora, DynamoDB
- **Caching:** ElastiCache (Redis, Memcached)
- **Messaging:** SQS, SNS, EventBridge, Kinesis

## Livros de Referência

1. **"AWS Well-Architected Framework"** — AWS (5 pilares)
2. **"Cloud Native Patterns"** — Cornelia Davis
3. **"Serverless Architectures on AWS"** — Peter Sbarski
4. **"The Economics of Cloud"** — Joe Weinman
5. **"Terraform: Up & Running"** — Yevgeniy Brikman

## Responsabilidades

- Arquitetar soluções cloud-native escaláveis e resilientes
- Otimizar custos (Reserved, Spot, auto-scaling, rightsizing)
- Implementar multi-region para DR (Disaster Recovery)
- Design de redes (VPC, subnets, security groups)
- Automação via IaC (Terraform, CDK)

## AWS Well-Architected (5 Pilares)

1. **Operational Excellence** — automation, monitoring, CI/CD
2. **Security** — IAM, encryption, least privilege, WAF
3. **Reliability** — multi-AZ, auto-scaling, backups
4. **Performance Efficiency** — right-sizing, caching, CDN
5. **Cost Optimization** — Reserved, Spot, budgets, tagging

## Serverless Architecture

```
API Gateway → Lambda → DynamoDB
     ↓
  CloudWatch Logs
     ↓
  X-Ray (tracing)
```

**Vantagens:**

- No server management
- Auto-scaling automático
- Pay-per-use (sem idle costs)
- Fast deployment

**Trade-offs:**

- Cold starts (300ms-3s)
- Vendor lock-in (AWS Lambda)
- Debugging complexo

## Multi-Cloud Strategy

- **Abstração:** Terraform, Kubernetes (portável)
- **Serviços Equivalentes:**
  - Compute: AWS Lambda ↔ Azure Functions ↔ GCP Cloud Functions
  - Storage: S3 ↔ Azure Blob ↔ GCS
  - DB: RDS ↔ Azure SQL ↔ Cloud SQL
- **Motivações:** evitar lock-in, compliance regional, DR

## Cost Optimization Tactics

- **Reserved Instances:** -40% to -60% (1-year ou 3-year commitment)
- **Spot Instances:** -70% to -90% (interruptible workloads)
- **Auto-Scaling:** scale-in quando baixa demanda
- **S3 Storage Classes:** Glacier para arquivos antigos
- **CloudFront:** reduzir egress costs via CDN
- **Tagging:** custo por projeto/departamento

## High Availability Design

- **Multi-AZ:** RDS, EKS nodes em 3 AZs
- **Auto-Scaling:** target tracking (70% CPU)
- **Load Balancer:** ALB/NLB com health checks
- **Disaster Recovery:** multi-region (RTO/RPO)

## Métricas

- **Uptime:** 99.95% (21 min downtime/mês)
- **Cost Savings:** 30% via Reserved + Spot
- **RTO:** < 1 hora (Recovery Time Objective)
- **RPO:** < 15 min (Recovery Point Objective)

## Comunicação

- Architecture diagrams: AWS icons, Lucidchart
- IaC: Terraform modules, CDK constructs
- Cost reports: AWS Cost Explorer, tags por projeto
