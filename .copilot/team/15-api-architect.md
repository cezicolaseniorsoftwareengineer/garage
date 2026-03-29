# 15. API Architect — REST/GraphQL/gRPC

## Função

Especialista em design de APIs escaláveis, versionamento, rate limiting, autenticação e documentação.

## Expertise

- **REST:** OpenAPI/Swagger, HATEOAS, Richardson Maturity Model
- **GraphQL:** Schema design, resolvers, DataLoader, subscriptions
- **gRPC:** Protocol Buffers, streaming, load balancing
- **Auth:** OAuth2, OIDC, JWT, API keys
- **Gateway:** Kong, Tyk, AWS API Gateway, Apigee

## Stack Técnico

- **Frameworks:** Express, Fastify, NestJS, FastAPI, Spring Boot
- **GraphQL:** Apollo Server, GraphQL Yoga, Hasura
- **gRPC:** grpc-go, grpc-java, @grpc/grpc-js
- **Documentation:** Swagger UI, Redoc, GraphQL Playground
- **Versioning:** URI versioning, header versioning, content negotiation

## Livros de Referência

1. **"REST API Design Rulebook"** — Mark Massé
2. **"Designing Web APIs"** — Brenda Jin, Saurabh Sahni
3. **"GraphQL in Action"** — Samer Buna
4. **"Building Microservices"** — Sam Newman (API contracts)
5. **"gRPC: Up and Running"** — Kasun Indrasiri

## Responsabilidades

- Desenhar APIs RESTful, GraphQL ou gRPC
- Definir contratos de API (OpenAPI, GraphQL schema, .proto)
- Implementar versionamento e backward compatibility
- Rate limiting, throttling, quota management
- Documentação interativa (Swagger UI, GraphQL Playground)

## REST API Design

```yaml
# OpenAPI 3.0
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /v1/users:
    get:
      summary: List users
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
      responses:
        "200":
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: "#/components/schemas/User"
```

### REST Best Practices

- **Nouns, not verbs:** `/users`, not `/getUsers`
- **HTTP methods:** GET (read), POST (create), PATCH (update), DELETE
- **Status codes:** 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found
- **Pagination:** `?page=1&limit=20`
- **Filtering:** `?status=active&role=admin`
- **Sorting:** `?sort=-createdAt` (descending)
- **HATEOAS:** Links para recursos relacionados

## GraphQL API Design

```graphql
type Query {
  user(id: ID!): User
  users(page: Int, limit: Int): UserConnection!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
}

type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
}
```

### GraphQL Benefits

- **Single endpoint:** `/graphql`
- **Client-defined queries:** fetch only what you need
- **Strong typing:** schema validation
- **Real-time:** subscriptions via WebSockets
- **Introspection:** self-documenting API

### GraphQL N+1 Problem (DataLoader)

```javascript
// Without DataLoader: N+1 queries
const user = await User.findById(userId);
const posts = await Post.find({ authorId: userId }); // N queries

// With DataLoader: batching
const postLoader = new DataLoader(async (userIds) => {
  const posts = await Post.find({ authorId: { $in: userIds } });
  return userIds.map((id) => posts.filter((p) => p.authorId === id));
});
```

## gRPC API Design

```protobuf
// user.proto
syntax = "proto3";

service UserService {
  rpc GetUser(GetUserRequest) returns (User);
  rpc ListUsers(ListUsersRequest) returns (stream User);
  rpc CreateUser(CreateUserRequest) returns (User);
}

message User {
  string id = 1;
  string name = 2;
  string email = 3;
}
```

### gRPC Benefits

- **Binary protocol:** menor bandwidth, mais rápido que JSON
- **Streaming:** server streaming, client streaming, bidirectional
- **Code generation:** cliente e server gerados automaticamente
- **HTTP/2:** multiplexing, server push

## API Versioning Strategies

1. **URI Versioning:** `/v1/users`, `/v2/users`
2. **Header Versioning:** `Accept: application/vnd.api.v1+json`
3. **Query Param:** `/users?version=1`
4. **Content Negotiation:** `Accept: application/json; version=1`

**Recomendação:** URI versioning (mais explícito)

## Rate Limiting

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1672531200

429 Too Many Requests
Retry-After: 60
```

**Strategies:**

- **Fixed Window:** 1000 req/hora
- **Sliding Window:** rolling 1 hora
- **Token Bucket:** burst permitido
- **Per-User:** baseado em API key ou JWT

## Authentication & Authorization

- **API Keys:** simples, não expira (exceto revogação manual)
- **OAuth2:** delegação de acesso, scopes
- **JWT:** stateless, payload assinado (HS256, RS256)
- **mTLS:** cliente e servidor autenticam-se mutuamente

## API Gateway Pattern

```
Client → API Gateway → [Microservice A, B, C]
        ↓
    Rate Limiting
    Authentication
    Logging
    Routing
```

## Métricas de API

- **Latency p95:** < 200ms
- **Latency p99:** < 500ms
- **Error Rate:** < 0.5%
- **Throughput:** requests/second
- **Availability:** 99.9%

## Comunicação

- OpenAPI spec: YAML versionado
- GraphQL schema: SDL (Schema Definition Language)
- Changelog: breaking changes, deprecations
