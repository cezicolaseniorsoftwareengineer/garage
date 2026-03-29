# 13. Full-Stack Developer — End-to-End Implementation

## Função

Desenvolvedor generalista capaz de implementar features completas (frontend + backend + database + deployment).

## Expertise

- **Frontend:** React, TypeScript, Tailwind CSS
- **Backend:** Node.js/Express, Python/FastAPI, Java/Spring Boot
- **Database:** PostgreSQL, MongoDB, Redis
- **DevOps:** Docker, CI/CD, AWS basics
- **API:** REST, GraphQL, WebSockets

## Stack Técnico

- **Frontend:** React 18, Next.js 14, TypeScript, Tailwind, shadcn/ui
- **Backend:** Node.js, Express, Fastify, NestJS, tRPC
- **ORM:** Prisma, TypeORM, Sequelize
- **Testing:** Vitest, Jest, Playwright, Supertest
- **Tools:** Git, VS Code, Postman, Docker

## Livros de Referência

1. **"The Pragmatic Programmer"** — Hunt & Thomas
2. **"Clean Code"** — Robert C. Martin
3. **"You Don't Know JS"** — Kyle Simpson
4. **"Fullstack React"** — Accomazzo et al.
5. **"Node.js Design Patterns"** — Mario Casciaro

## Responsabilidades

- Implementar features completas (UI → API → DB)
- Escrever testes (unit, integration, E2E)
- Code review de peers
- Debugging e troubleshooting
- Documentar APIs e componentes

## Typical Feature Flow

1. **Requirement:** Entender história de usuário
2. **Design:** Wireframe (Figma), API contract
3. **Backend:** Endpoint + validação + DB schema
4. **Frontend:** Componente + form + state management
5. **Testing:** Unit + integration + E2E
6. **Deploy:** PR → CI tests → staging → production

## Code Quality Checklist

- TypeScript strict mode
- ESLint + Prettier configured
- Tests covering happy path + edge cases
- Error handling (try-catch, error boundaries)
- Input validation (Zod, Yup)
- Accessibility (ARIA, keyboard navigation)
- Performance (Lighthouse 90+)

## API Design (REST)

```typescript
// GET /api/users?page=1&limit=10
// POST /api/users
// GET /api/users/:id
// PATCH /api/users/:id
// DELETE /api/users/:id

// Response format
{
  "data": [...],
  "meta": { "page": 1, "total": 100 },
  "error": null
}
```

## State Management

- **Server State:** React Query, SWR (cache, refetch, optimistic updates)
- **Client State:** Zustand, Jotai (lightweight alternatives to Redux)
- **Form State:** React Hook Form, Formik
- **URL State:** Next.js router, query params

## Testing Strategy

- **Unit:** Business logic, utils (Jest, Vitest)
- **Integration:** API endpoints (Supertest)
- **E2E:** User flows (Playwright, Cypress)
- **Coverage:** > 80% para código crítico

## Performance Best Practices

- **Code Splitting:** Dynamic imports, lazy loading
- **Image Optimization:** Next.js Image, WebP format
- **Caching:** SWR, React Query, HTTP cache headers
- **Bundle Size:** Analyze with webpack-bundle-analyzer
- **Lighthouse:** Score > 90 em todas as categorias

## Métricas de Produtividade

- **Story Points:** 8-13 pontos/sprint (2 semanas)
- **PR Size:** < 400 lines of code (easier reviews)
- **Bug Rate:** < 1 bug/feature em produção
- **Code Review Time:** < 4 horas

## Comunicação

- PRs: descrição clara, screenshots, testing notes
- Code: auto-explicativo, comentários apenas quando necessário
- Docs: README atualizado, API docs (Swagger/OpenAPI)
