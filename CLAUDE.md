# CLAUDE.md — Assist CLI

## Project Overview

Assist CLI is a modular coding assistant built around:
- CLI-first interaction
- declarative routing
- lightweight specialized agents
- filesystem-based skills
- self-validation loops
- global verification layer
- deterministic testing

The project is designed for:
- real-world usage
- maintainability
- offline testability
- clean architecture

---

# Core Architectural Principles

## 1. Single Responsibility

Every module must have one clear responsibility.

Examples:
- CLI handles parsing and terminal interaction
- Registry defines routing
- Orchestrator coordinates flow
- Agents generate outputs
- Verifier validates outputs

Do not mix responsibilities.

---

## 2. Registry Is the Source of Truth

Routing logic MUST NOT be hardcoded.

Allowed:
- config/registry.yaml

Forbidden:
- if/else routing inside orchestrator
- task-agent mapping inside agents
- routing logic inside CLI

---

## 3. Agents Must Stay Lightweight

Agents:
- receive tasks
- receive skills
- generate drafts
- self-check outputs

Agents MUST NOT:
- perform routing
- access filesystem directly
- assemble final output
- call other agents

---

## 4. Skills Are Operational Knowledge

Skills are stored as filesystem resources.

Location:
assist/skills/<skill_name>/SKILL.md

Skills contain:
- rules
- constraints
- examples
- templates
- formatting expectations

Skills are NOT agents.

---

## 5. Deterministic Testing First

The system must be testable offline.

Rules:
- all tests use MockLLMClient
- no real API calls during unit tests
- every core component must be mockable

---

## 6. Strong Typing Everywhere

Rules:
- Pydantic v2 for cross-module data
- type hints required on public APIs
- no untyped dicts between modules

Forbidden:
- Any
- implicit payload structures
- dynamically shaped responses

---

## 7. Self-Validation Rules

Each agent performs:
1. draft generation
2. self-check
3. correction
4. optional recheck

Constraints:
- max 2 correction loops
- self-check prompts must be critical
- failed convergence returns best draft + warning

---

## 8. Verification Layer Rules

The Global Verification Layer validates:
- syntax
- structure
- coherence
- placeholders
- output integrity

Verification should prefer deterministic checks whenever possible.

Prefer:
- ast.parse()
- regex
- Pydantic validation

Avoid unnecessary LLM calls.

---

# Forbidden Patterns

## Forbidden Globally

- direct model calls outside assist/llm/
- routing logic outside registry.yaml
- circular imports
- business logic in CLI layer
- hidden mutable global state
- silent exception swallowing

---

# Coding Standards

## Python

- Python 3.10+
- use pathlib instead of os.path when possible
- explicit return types required
- prefer composition over inheritance

---

## Naming

### Functions
snake_case

### Classes
PascalCase

### Constants
UPPER_SNAKE_CASE

---

## Formatting

- concise code
- avoid overengineering
- avoid nested conditionals when possible
- keep functions small and focused

---

# Testing Requirements

Every core module should eventually have:
- unit tests
- failure tests
- edge case tests

Critical invariants:
- self-check loop never exceeds limit
- verifier never validates empty output
- registry never raises raw KeyError
- AgentOutput quality_score always between 0 and 1

---

# Project Philosophy

The goal is NOT:
- building a flashy AI demo
- maximizing features
- simulating AGI

The goal IS:
- building a reliable developer tool
- producing clean outputs
- enforcing quality
- keeping architecture maintainable