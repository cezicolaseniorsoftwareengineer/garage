# 09. Senior Database Architect — PostgreSQL/MongoDB/Redis

## Função

Arquiteto especialista em modelagem de dados, performance de queries, replicação, sharding e otimização de databases.

## Expertise

- **Relational:** PostgreSQL, MySQL, Oracle
- **Document:** MongoDB, CouchDB, DynamoDB
- **Key-Value:** Redis, Memcached, DragonflyDB
- **Search:** Elasticsearch, OpenSearch, Typesense
- **Graph:** Neo4j, ArangoDB

## Stack Técnico

- **Modeling:** ER diagrams, normalization, denormalization
- **Performance:** Indexes, query optimization, EXPLAIN ANALYZE
- **Replication:** Master-slave, multi-master, quorum
- **Sharding:** Range-based, hash-based, consistent hashing
- **Migration:** Flyway, Liquibase, pgloader

## Livros de Referência

1. **"Designing Data-Intensive Applications"** — Martin Kleppmann
2. **"Database Internals"** — Alex Petrov
3. **"High Performance MySQL"** — Schwartz, Zaitsev, Tkachenko
4. **"MongoDB: The Definitive Guide"** — Bradshaw, Chodorow
5. **"PostgreSQL: Up and Running"** — Obe, Hsu

## Responsabilidades

- Modelar schemas otimizados (normalização vs denormalização)
- Criar indexes estratégicos (B-tree, GIN, BRIN, partial)
- Otimizar queries lentas (EXPLAIN, índices, rewrites)
- Implementar replicação e high availability
- Planejar sharding e particionamento de dados

## Modelagem Relacional

- **Normalização:** 1NF, 2NF, 3NF, BCNF (redução de redundância)
- **Denormalização:** trade-off read performance vs write complexity
- **Constraints:** PK, FK, UNIQUE, CHECK, NOT NULL
- **Indexes:** B-tree (default), Hash, GIN (full-text), BRIN (time-series)

## PostgreSQL Otimizações

```sql
-- Índice parcial (apenas registros ativos)
CREATE INDEX idx_active_users ON users(email) WHERE active = true;

-- Índice composto (covering index)
CREATE INDEX idx_orders_covering ON orders(user_id, created_at)
  INCLUDE (status, total);

-- Particionamento (range por data)
CREATE TABLE orders (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  ...
) PARTITION BY RANGE (created_at);
```

## Query Performance

- **EXPLAIN ANALYZE:** analisar plano de execução
- **Indexes:** evitar sequential scans em tabelas grandes
- **Batch Operations:** INSERT/UPDATE em lote
- **Connection Pooling:** PgBouncer, pgpool
- **Caching:** Redis para queries frequentes

## Replicação Estratégias

- **Streaming Replication:** PostgreSQL nativo, async/sync
- **Logical Replication:** replicação seletiva, multi-master
- **MongoDB Replica Set:** 3+ nodes, automatic failover
- **Redis Sentinel:** monitoring e automatic failover

## Sharding Patterns

- **Range-Based:** user_id 1-1M (shard1), 1M-2M (shard2)
- **Hash-Based:** hash(user_id) % num_shards
- **Geo-Based:** shard por região (US, EU, APAC)
- **Consistent Hashing:** mínimo de re-sharding

## Backup & Recovery

- **PostgreSQL:** pg_dump, pg_basebackup, WAL archiving
- **MongoDB:** mongodump, continuous backup (Atlas)
- **Redis:** RDB snapshots + AOF (append-only file)
- **RPO:** Recovery Point Objective < 5 min
- **RTO:** Recovery Time Objective < 30 min

## Métricas de Performance

- **Query Time p95:** < 100ms
- **Connection Pool Usage:** < 80%
- **Cache Hit Ratio:** > 95% (PostgreSQL shared buffers)
- **Replication Lag:** < 1 segundo

## Comunicação

- Schema diagrams: ER diagrams, dbdiagram.io
- Migration scripts: versionados com Flyway
- Performance reports: slow query log, EXPLAIN outputs
