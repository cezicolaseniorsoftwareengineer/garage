# Biblioteca Mestra de Tecnologia — Cezi Cola

## Propósito

Base operacional expandida para o cérebro do Cezi com 25 referências técnicas. O objetivo é manter decisões consistentes em arquitetura, integração, persistência, JSON, observabilidade, frontend, backend e orquestração.

## Livros Prioritários

1. **Clean Code** — Robert C. Martin
   Responsabilidade: legibilidade, naming, funções pequenas, disciplina de refatoração.

2. **Clean Architecture** — Robert C. Martin
   Responsabilidade: boundaries, dependency rule, separação entre domínio, aplicação e adapters.

3. **Test-Driven Development: By Example** — Kent Beck
   Responsabilidade: ciclo red-green-refactor, design orientado por testes.

4. **Refactoring** — Martin Fowler
   Responsabilidade: evolução segura do código, simplificação incremental.

5. **Patterns of Enterprise Application Architecture** — Martin Fowler
   Responsabilidade: repository, unit of work, DTO, service layer, transaction patterns.

6. **Domain-Driven Design** — Eric Evans
   Responsabilidade: ubiquitous language, bounded contexts, aggregates.

7. **Implementing Domain-Driven Design** — Vaughn Vernon
   Responsabilidade: tactical DDD, integração entre contextos, aggregates enxutos.

8. **Building Microservices** — Sam Newman
   Responsabilidade: decomposição, autonomia, resiliência, integração de serviços.

9. **Designing Data-Intensive Applications** — Martin Kleppmann
   Responsabilidade: persistência, replicação, particionamento, consistência, eventos.

10. **Release It!** — Michael Nygard
    Responsabilidade: circuit breaker, bulkhead, timeout, backpressure, estabilidade em produção.

11. **Enterprise Integration Patterns** — Gregor Hohpe e Bobby Woolf
    Responsabilidade: orquestração, mensageria, contratos, roteamento, transformação de payloads e JSON.

12. **Fundamentals of Software Architecture** — Mark Richards e Neal Ford
    Responsabilidade: trade-offs arquiteturais, estilos, qualidade de atributos.

13. **Architecture Patterns with Python** — Harry Percival e Bob Gregory
    Responsabilidade: ports and adapters, unit of work, events, service layer em Python.

14. **Spring in Action** — Craig Walls
    Responsabilidade: Spring Boot, DI, web, segurança, integração enterprise em Java.

15. **Django for APIs** — William S. Vincent
    Responsabilidade: APIs robustas, organização de projeto Django, autenticação e serializers.

16. **FastAPI: Modern Python Web Development** — Bill Lubanovic
    Responsabilidade: APIs assíncronas, tipagem, validação, OpenAPI, performance.

17. **Continuous Delivery** — Jez Humble e David Farley
    Responsabilidade: pipelines, deploy seguro, automação ponta a ponta.

18. **Accelerate** — Nicole Forsgren, Jez Humble e Gene Kim
    Responsabilidade: métricas de entrega, fluxo, estabilidade, excelência operacional.

19. **Site Reliability Engineering** — Google
    Responsabilidade: SLO, error budget, incident response, operação confiável.

20. **Kubernetes in Action** — Marko Lukša
    Responsabilidade: orquestração de workloads, config, secrets, scaling, runtime cloud-native.

21. **Systems Performance** — Brendan Gregg
    Responsabilidade: profiling, tracing, análise de gargalos, USE/RED.

22. **Introduction to Algorithms** — Cormen, Leiserson, Rivest, Stein
    Responsabilidade: estruturas de dados, complexidade, grafos, otimização algorítmica.

23. **Refactoring UI** — Adam Wathan e Steve Schoger
    Responsabilidade: hierarquia visual, consistência, ergonomia e design de interface.

24. **Don't Make Me Think** — Steve Krug
    Responsabilidade: usabilidade, clareza cognitiva, fluxo do usuário.

25. **Atomic Design** — Brad Frost
    Responsabilidade: design systems, componentes, composição de interface.

## Regras de Aplicação no Cezi

- Backend, frontend e banco devem ser modelados como um fluxo único de negócio.
- Contratos JSON devem ser estáveis, versionados e compatíveis com validação de schema.
- Persistência deve refletir regras de domínio, não atalhos de framework.
- Integração entre front e back deve considerar estado, erro, loading, segurança e observabilidade.
- Toda orquestração deve explicitar contrato, retries, idempotência e compensação quando aplicável.

## Ativação Recomendada

Para problemas complexos, usar esta base em conjunto com:

- `.copilot/prompts/cezicola.md`
- `.copilot/masters/23-masters-council.md`
- `.copilot/team/03-lead-backend.md`
- `.copilot/team/04-lead-frontend.md`
- `.copilot/team/09-database-architect.md`
- `.copilot/team/15-api-architect.md`
