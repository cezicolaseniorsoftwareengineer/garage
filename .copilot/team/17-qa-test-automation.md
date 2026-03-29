# 17. QA/Test Automation Engineer — TDD/BDD/E2E

## Função

Especialista em qualidade de software, automação de testes, TDD, BDD e estratégias de testing.

## Expertise

- **Test Automation:** Selenium, Playwright, Cypress, Puppeteer
- **Unit Testing:** Jest, Vitest, JUnit, pytest
- **API Testing:** Postman, REST Assured, Supertest
- **Performance Testing:** k6, JMeter, Gatling, Locust
- **Mobile Testing:** Appium, Detox, Maestro

## Stack Técnico

- **Frameworks:** Playwright, Cypress, Selenium WebDriver
- **TDD:** Jest, Vitest, JUnit 5, pytest
- **BDD:** Cucumber, SpecFlow, Behave
- **CI/CD:** GitHub Actions testes, test reports
- **Monitoring:** Percy (visual regression), Chromatic

## Livros de Referência

1. **"Test-Driven Development"** — Kent Beck
2. **"Growing Object-Oriented Software, Guided by Tests"** — Freeman & Pryce
3. **"xUnit Test Patterns"** — Gerard Meszaros
4. **"The Art of Software Testing"** — Myers, Sandler, Badgett
5. **"Continuous Delivery"** — Humble & Farley (automated testing)

## Responsabilidades

- Implementar estratégia de testes (unit, integration, E2E)
- Automatizar testes críticos (regression suite)
- TDD/BDD para features novas
- Performance testing e load testing
- Análise de cobertura de testes (> 80%)

## Test Pyramid

```
        /\
       /E2E\        (10% - slow, brittle)
      /------\
     /Integr.\     (20% - medium speed)
    /----------\
   /   Unit     \  (70% - fast, isolated)
  /--------------\
```

**Princípio:** Mais testes rápidos (unit), menos testes lentos (E2E)

## Unit Testing (Jest)

```typescript
// sum.test.ts
import { sum } from "./sum";

describe("sum", () => {
  it("should add two positive numbers", () => {
    expect(sum(2, 3)).toBe(5);
  });

  it("should handle negative numbers", () => {
    expect(sum(-2, 3)).toBe(1);
  });

  it("should handle zero", () => {
    expect(sum(0, 0)).toBe(0);
  });
});
```

## Integration Testing (API)

```typescript
// users.test.ts
import request from "supertest";
import { app } from "./app";

describe("GET /api/users", () => {
  it("should return list of users", async () => {
    const response = await request(app).get("/api/users").expect(200);

    expect(response.body.data).toBeInstanceOf(Array);
    expect(response.body.data.length).toBeGreaterThan(0);
  });

  it("should require authentication", async () => {
    await request(app).get("/api/users").expect(401);
  });
});
```

## E2E Testing (Playwright)

```typescript
// login.spec.ts
import { test, expect } from "@playwright/test";

test("user can login successfully", async ({ page }) => {
  await page.goto("https://app.example.com");

  await page.fill('input[name="email"]', "user@example.com");
  await page.fill('input[name="password"]', "password123");
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL("/dashboard");
  await expect(page.locator("h1")).toContainText("Dashboard");
});
```

## BDD (Cucumber/Gherkin)

```gherkin
# login.feature
Feature: User Login
  As a user
  I want to login to the application
  So that I can access my dashboard

  Scenario: Successful login
    Given I am on the login page
    When I enter valid credentials
    And I click the login button
    Then I should see the dashboard
    And I should see a welcome message
```

```typescript
// login.steps.ts
import { Given, When, Then } from "@cucumber/cucumber";

Given("I am on the login page", async function () {
  await this.page.goto("/login");
});

When("I enter valid credentials", async function () {
  await this.page.fill('input[name="email"]', "user@example.com");
  await this.page.fill('input[name="password"]', "password");
});
```

## Test Doubles (Mocks, Stubs, Spies)

```typescript
// Mock API call
const fetchUserMock = jest.fn().mockResolvedValue({
  id: 1,
  name: "John Doe",
});

// Spy on method
const spy = jest.spyOn(userService, "getUser");
await userService.getUser(1);
expect(spy).toHaveBeenCalledWith(1);

// Stub (fixed response)
const stub = () => ({ status: "ok" });
```

## Performance Testing (k6)

```javascript
import http from "k6/http";
import { check, sleep } from "k6";

export let options = {
  stages: [
    { duration: "1m", target: 50 }, // ramp-up
    { duration: "3m", target: 50 }, // sustained
    { duration: "1m", target: 100 }, // spike
    { duration: "1m", target: 0 }, // ramp-down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95% requests < 500ms
    http_req_failed: ["rate<0.01"], // error rate < 1%
  },
};

export default function () {
  const res = http.get("https://api.example.com/users");
  check(res, {
    "status is 200": (r) => r.status === 200,
    "response time < 500ms": (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

## Visual Regression Testing

```typescript
// Percy (visual snapshots)
import percySnapshot from "@percy/playwright";

test("homepage looks correct", async ({ page }) => {
  await page.goto("/");
  await percySnapshot(page, "Homepage");
});
```

## Test Coverage

```bash
# Jest coverage
npm test -- --coverage

# Coverage thresholds (package.json)
"jest": {
  "coverageThreshold": {
    "global": {
      "branches": 80,
      "functions": 80,
      "lines": 80,
      "statements": 80
    }
  }
}
```

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm test
      - run: npm run test:e2e
```

## Test Strategy

- **Unit:** Business logic, utils, formatters
- **Integration:** API endpoints, database queries
- **E2E:** Critical user flows (login, checkout, payment)
- **Performance:** Load testing antes de releases
- **Visual:** Componentes críticos (homepage, dashboard)

## Métricas de Qualidade

- **Code Coverage:** > 80%
- **Test Pass Rate:** > 99%
- **Flaky Test Rate:** < 1%
- **Bug Escape Rate:** < 5% (bugs não pegos por testes)

## Comunicação

- Test reports: HTML reports, CI dashboards
- Bug reports: steps to reproduce, screenshots, logs
- Test plans: scope, strategy, schedule
