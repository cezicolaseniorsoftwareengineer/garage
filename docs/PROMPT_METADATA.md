# Prompt Metadata and Tag Schema

This document specifies the minimal metadata schema for prompts used by `Cezi Cola` agents.

Fields (YAML):

- `id`: unique prompt id
- `title`: short description
- `state`: one of `[RISK, DECISION, CONSEQUENCE, IMPLEMENTATION]`
- `model_hint`: preferred model or role
- `language`: `pt-BR` or `en` (prompt content language)
- `sensitivity`: `low|medium|high`

Example:

```yaml
id: prompt-001
title: Validate transaction schema
state: DECISION
model_hint: GPT-5 mini
language: en
sensitivity: high
```

Store prompt metadata alongside prompts. Use `templates/prompt_template.yaml` for new prompts.
