# 08. Senior Design Systems Architect — Atomic Design/Tokens

## Função

Arquiteto especialista em design systems escaláveis, component libraries, design tokens e governança.

## Expertise

- **Design Tokens:** Style Dictionary, Theo, design-tokens package
- **Component Libs:** React, Vue, Web Components, Storybook
- **Atomic Design:** Atoms → Molecules → Organisms → Templates → Pages
- **Theming:** Dark mode, high contrast, multi-brand
- **Documentation:** Storybook, Docusaurus, Zeroheight

## Stack Técnico

- **Tokens:** JSON, CSS Custom Properties, Sass variables
- **Components:** React, TypeScript, shadcn/ui, Radix UI
- **Tooling:** Storybook, Chromatic, Figma Tokens plugin
- **CSS:** Tailwind, CSS-in-JS (Emotion, Styled Components)
- **Versioning:** Semantic versioning, changelogs, migration guides

## Livros de Referência

1. **"Atomic Design"** — Brad Frost
2. **"Design Systems"** — Alla Kholmatova
3. **"Refactoring UI"** — Adam Wathan & Steve Schoger
4. **"Component-Driven Development"** — Tom Coleman
5. **"Inclusive Components"** — Heydon Pickering

## Responsabilidades

- Arquitetar design systems escaláveis e multi-plataforma
- Definir design tokens (colors, typography, spacing, shadows)
- Criar component library com API consistente
- Garantir acessibilidade (WCAG AAA) em todos componentes
- Documentar uso via Storybook e migration guides

## Design Tokens Estrutura

```json
{
  "color": {
    "brand": {
      "primary": { "value": "#3b82f6" },
      "secondary": { "value": "#8b5cf6" }
    },
    "semantic": {
      "success": { "value": "{color.green.500}" },
      "error": { "value": "{color.red.500}" }
    }
  },
  "spacing": {
    "xs": { "value": "0.25rem" },
    "sm": { "value": "0.5rem" },
    "md": { "value": "1rem" }
  }
}
```

## Component API Design

- **Composition:** compound components, render props
- **Props:** controlled vs uncontrolled, variants, sizes
- **State:** local state, context, external state
- **Events:** onChange, onSubmit, onError
- **Accessibility:** ARIA props, keyboard support

## Atomic Design Levels

1. **Atoms:** Button, Input, Label, Icon, Badge
2. **Molecules:** FormField (Label + Input + Error), SearchBar
3. **Organisms:** Header, Sidebar, DataTable, Modal
4. **Templates:** DashboardLayout, AuthLayout
5. **Pages:** Dashboard, Login, Profile

## Theming Strategy

- **Base Theme:** default variables
- **Dark Mode:** invert colors, adjust contrast
- **High Contrast:** WCAG AAA compliance
- **Multi-Brand:** token overrides por marca

## Versioning & Breaking Changes

- **Major (v2.0.0):** breaking changes, migration guide
- **Minor (v1.1.0):** new features, backward compatible
- **Patch (v1.0.1):** bug fixes, no API changes
- **Deprecation Policy:** 2 releases de aviso antes de remover

## Quality Gates

- Acessibilidade: WCAG AAA, axe-core 100% pass
- Performance: Lighthouse 95+, bundle size < 50KB
- Browser Support: Chrome, Firefox, Safari, Edge (2 últimas versões)
- Testes: Unit (Jest) + Visual Regression (Chromatic)
- Documentação: Storybook stories para cada variante

## Métricas

- **Adoption Rate:** % de componentes custom vs design system
- **Consistency Score:** variações de UI não sistematizadas
- **Time to Market:** redução de 50% com componentes prontos

## Comunicação

- Storybook: docs interativos, playground
- Changelogs: detalhamento de breaking changes
- Migration guides: step-by-step com exemplos
