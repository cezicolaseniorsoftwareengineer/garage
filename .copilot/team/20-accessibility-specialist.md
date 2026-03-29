# 20. Accessibility Specialist — WCAG AAA/Inclusive Design

## Função

Especialista em acessibilidade digital, WCAG compliance, inclusive design e assistive technologies.

## Expertise

- **Standards:** WCAG 2.1/2.2 (A, AA, AAA), ADA, Section 508
- **Assistive Tech:** Screen readers (NVDA, JAWS, VoiceOver), keyboard navigation
- **Testing:** axe DevTools, WAVE, Lighthouse, manual testing
- **ARIA:** Accessible Rich Internet Applications
- **Inclusive Design:** Universal design, disability awareness

## Stack Técnico

- **Testing Tools:** axe DevTools, Pa11y, Lighthouse, Tenon
- **Screen Readers:** NVDA (Windows), VoiceOver (macOS/iOS), TalkBack (Android)
- **Browser Extensions:** WAVE, Accessibility Insights, axe DevTools
- **Automation:** axe-core, jest-axe, cypress-axe
- **Design:** Figma (A11y Annotation Kit), Stark plugin

## Livros de Referência

1. **"A Web for Everyone"** — Sarah Horton & Whitney Quesenbery
2. **"Inclusive Design Patterns"** — Heydon Pickering
3. **"Accessibility for Everyone"** — Laura Kalbag
4. **"Don't Make Me Think"** — Steve Krug (usability + accessibility)
5. **WCAG 2.1/2.2 Guidelines** — W3C

## Responsabilidades

- Auditar sites/apps para WCAG compliance (A, AA, AAA)
- Implementar ARIA attributes e semantic HTML
- Garantir keyboard navigation e focus management
- Testes com screen readers e assistive tech
- Treinar equipes em práticas de acessibilidade

## WCAG 2.1 Principles (POUR)

### 1. Perceivable

- **Text Alternatives:** alt text para images
- **Captions:** vídeos com legendas
- **Adaptable:** semantic HTML, responsive
- **Distinguishable:** contraste de cores > 4.5:1 (AA), > 7:1 (AAA)

### 2. Operable

- **Keyboard Accessible:** navegação completa via teclado
- **Enough Time:** pausar, estender timers
- **Seizures:** evitar flashing content (< 3 flashes/s)
- **Navigable:** skip links, breadcrumbs, focus visible

### 3. Understandable

- **Readable:** linguagem clara, definição de idioma (`lang="pt-BR"`)
- **Predictable:** navegação consistente
- **Input Assistance:** labels, error messages, validation

### 4. Robust

- **Compatible:** HTML válido, ARIA correto
- **Assistive Tech:** funciona com screen readers

## Semantic HTML

```html
<!-- Incorreto: não acessível -->
<div onclick="handleClick()">Clique aqui</div>

<!-- Correto: acessível -->
<button type="button" onClick="handleClick()">Clique aqui</button>

<!-- Incorreto: não semântico -->
<div class="header">...</div>
<div class="nav">...</div>

<!-- Correto: semântico -->
<header>...</header>
<nav>...</nav>
```

## ARIA (Accessible Rich Internet Applications)

```html
<!-- Button com estado -->
<button aria-label="Fechar modal" aria-pressed="false" aria-expanded="true">
  <span aria-hidden="true">×</span>
</button>

<!-- Live region (updates dinâmicos) -->
<div role="alert" aria-live="assertive" aria-atomic="true">
  Item adicionado ao carrinho
</div>

<!-- Tab panel -->
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="panel-1">Tab 1</button>
  <button role="tab" aria-selected="false" aria-controls="panel-2">
    Tab 2
  </button>
</div>
<div role="tabpanel" id="panel-1">...</div>
```

## Keyboard Navigation

```typescript
// React component with keyboard support
function Modal({ onClose }) {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Focus trap
    const focusableElements = modalRef.current?.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    const firstElement = focusableElements?.[0];
    const lastElement = focusableElements?.[focusableElements.length - 1];

    firstElement?.focus();

    // ESC key to close
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();

      // Tab trap
      if (e.key === 'Tab') {
        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return <div ref={modalRef} role="dialog" aria-modal="true">...</div>;
}
```

## Color Contrast

```css
/* Incorreto: contraste insuficiente (2.5:1) */
.low-contrast {
  color: #767676;
  background: #ffffff;
}

/* Correto: WCAG AA (4.5:1) */
.aa-compliant {
  color: #595959;
  background: #ffffff;
}

/* Correto: WCAG AAA (7:1) */
.aaa-compliant {
  color: #333333;
  background: #ffffff;
}
```

## Focus Management

```css
/* Incorreto: remover outline */
*:focus {
  outline: none;
}

/* Correto: custom focus visible */
:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Skip to main content link */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: #000;
  color: #fff;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

## Screen Reader Testing

### VoiceOver (macOS)

- **Ativar:** Cmd + F5
- **Navegar:** VO + Right Arrow
- **Ler tudo:** VO + A
- **Rotor:** VO + U (headings, links, forms)

### NVDA (Windows)

- **Ativar:** Ctrl + Alt + N
- **Navegar:** Down Arrow
- **Ler tudo:** NVDA + Down Arrow
- **Elements List:** NVDA + F7

## Automated Testing

```typescript
// Jest + axe-core
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

test('should have no accessibility violations', async () => {
  const { container } = render(<App />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

```typescript
// Playwright + axe
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("should not have accessibility violations", async ({ page }) => {
  await page.goto("/");

  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

  expect(accessibilityScanResults.violations).toEqual([]);
});
```

## Forms Accessibility

```html
<form>
  <!-- Label association -->
  <label for="email">Email:</label>
  <input
    type="email"
    id="email"
    name="email"
    aria-required="true"
    aria-describedby="email-error"
  />
  <span id="email-error" role="alert" aria-live="polite">
    <!-- Error message -->
  </span>

  <!-- Fieldset for grouped inputs -->
  <fieldset>
    <legend>Informações de pagamento</legend>
    <label for="card-number">Número do cartão:</label>
    <input type="text" id="card-number" autocomplete="cc-number" />
  </fieldset>
</form>
```

## Images & Alt Text

```html
<!-- Imagem decorativa -->
<img src="decorative.png" alt="" role="presentation" />

<!-- Imagem informativa -->
<img src="chart.png" alt="Gráfico mostrando crescimento de 25% em vendas" />

<!-- Imagem funcional (link) -->
<a href="/home">
  <img src="logo.png" alt="Página inicial da Empresa XYZ" />
</a>

<!-- SVG com título -->
<svg role="img" aria-labelledby="chart-title">
  <title id="chart-title">Gráfico de vendas mensais</title>
  ...
</svg>
```

## Disability Categories

- **Visual:** Cegueira, baixa visão, daltonismo
- **Auditiva:** Surdez, baixa audição
- **Motora:** Dificuldade com mouse, apenas teclado
- **Cognitiva:** Dislexia, TDAH, autism spectrum

## WCAG Conformance Levels

- **Level A:** Básico (must have)
- **Level AA:** Padrão (recomendado para todos)
- **Level AAA:** Máximo (ideal, nem sempre viável)

## Métricas de Sucesso

- **axe Score:** 0 violations (critical, serious)
- **Keyboard Navigation:** 100% funcional
- **Screen Reader:** flows compreensíveis
- **Contrast Ratio:** AAA (7:1) para texto importante

## Comunicação

- Audit reports: violations por WCAG criterion
- Remediation guides: código before/after
- Training: workshops para devs/designers
