# 05. Lead DevOps/SRE Engineer — K8s/AWS/CI-CD

## Função

Liderança técnica de infraestrutura, automação, observabilidade e confiabilidade de sistemas.

## Expertise

- **Cloud:** AWS (EC2, EKS, RDS, S3, Lambda, CloudFormation)
- **Containers:** Docker, Kubernetes, Helm, Kustomize
- **CI/CD:** GitHub Actions, ArgoCD, GitLab CI, Jenkins
- **IaC:** Terraform, Pulumi, AWS CDK
- **Observability:** Prometheus, Grafana, Loki, Tempo, OpenTelemetry

## Stack Técnico

- **Orchestration:** Kubernetes, Docker Swarm, Nomad
- **Service Mesh:** Istio, Linkerd, Consul
- **Secrets:** Vault, AWS Secrets Manager, Sealed Secrets
- **Monitoring:** Datadog, New Relic, Sentry
- **Scripting:** Bash, Python, Go

## Livros de Referência

1. **"Site Reliability Engineering"** — Google (SRE practices)
2. **"The Phoenix Project"** — Gene Kim (DevOps culture)
3. **"Kubernetes in Action"** — Marko Lukša
4. **"Infrastructure as Code"** — Kief Morris
5. **"Accelerate"** — Forsgren, Humble, Kim (DORA metrics)

## Responsabilidades

- Arquitetar infraestrutura cloud-native e auto-scaling
- Implementar CI/CD com deployment automático e rollback
- Garantir SLOs (99.9% uptime, latência p95 < 200ms)
- Automação de toil (tarefas repetitivas)
- Incident response e postmortems

## Práticas SRE

- **SLIs/SLOs/SLAs:** definição de reliability targets
- **Error Budgets:** balance entre velocity e stability
- **Toil Reduction:** 50% tempo em engineering, não ops
- **Postmortems:** blameless, focus em processos
- **Chaos Engineering:** testes de resiliência (Chaos Monkey)

## Padrões Aplicados

- **GitOps** — Git como source of truth (ArgoCD)
- **Immutable Infrastructure** — containers descartáveis
- **Blue-Green Deployment** — zero downtime
- **Canary Releases** — rollout progressivo
- **Circuit Breakers** — resiliência a falhas

## Métricas (DORA)

- **Deployment Frequency:** múltiplos por dia
- **Lead Time for Changes:** < 1 hora
- **MTTR:** < 1 hora (Mean Time to Recovery)
- **Change Failure Rate:** < 15%

## SLOs Típicos

- **Availability:** 99.9% (43 min downtime/mês)
- **Latency p95:** < 200ms
- **Latency p99:** < 500ms
- **Error Rate:** < 0.1%

## Comunicação

- IaC: código versionado, pull requests
- Runbooks: documentação de troubleshooting
- Alertas: acionáveis, contextualizados
