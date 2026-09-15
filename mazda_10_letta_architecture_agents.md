# Mazda Deterministic-First Refactor
## Build Plan for 10 Parallel Letta Architecture Agents

**Audience:** On-machine coding/orchestration agent  
**Phase:** Architecture only  
**Goal:** Create 10 specialized Letta agents that design the interface contracts for the Mazda deterministic-first refactor.

---

# 1. Mission

Create **10 specialized Letta agents** that can work in parallel on the architecture of the new Mazda finance workflow.

These agents are **not allowed to implement business logic yet**.

Their job is to design:

- Python `Protocol` interfaces
- Python `ABC` interfaces only where useful
- frozen `dataclass` or Pydantic contract models
- `Enum` types
- TypeScript interfaces/types where the browser/UI boundary needs them
- dependency rules
- contract tests/stubs if needed to prove architecture boundaries
- short architecture notes

They should **not** implement:

- scanner drivers
- Mazda calls
- persistence logic
- matching logic
- report generation
- Excel mutation
- calculations
- category logic
- vendor logic
- reconciliation logic
- agent orchestration behavior
- business rules

The point of this phase is to define the **ports and contracts** before implementation.

---

# 2. Architectural Rule

The new system should follow this operating model:

```text
CODE
  ↓ if unresolved
MAZDA
  ↓ if still unresolved / invalid
HUMAN
```

For scanner-triggered intake:

```text
Freezer Scanner UI ─┐
                    ├──> ProcessScanCommand
Window Scanner UI ──┘
                              │
                              ▼
                         IntakeFacade
                              │
                              ▼
                 Deterministic Intake Pipeline
                              │
                   ┌──────────┴──────────┐
                   │                     │
                COMPLETE          NEEDS_JUDGMENT
                   │                     │
                   │                     ▼
                   │                   Mazda
                   │                     │
                   └──────────────┬──────┘
                                  ▼
                         Deterministic Validation
                                  │
                         ┌────────┴────────┐
                         │                 │
                       VALID          HUMAN_REVIEW
                         │
                         ▼
                   Commit / Projections
```

The **UI must never call Mazda directly**.

Mazda is a reasoning Strategy inside the application workflow.

---

# 3. Shared Rules for All 10 Letta Agents

Every agent should receive these rules in its system prompt.

## 3.1 Architecture-only rule

Do not write concrete implementations.

Allowed:

```python
class IVendorResolver(Protocol):
    def resolve(self, request: VendorResolutionRequest) -> Resolution:
        ...
```

Not allowed:

```python
class VendorResolver:
    def resolve(self, request):
        # actual lookup logic
        ...
```

## 3.2 GoF rule

Prefer clear GoF boundaries where they fit naturally:

- Facade
- Command
- Adapter
- Bridge
- Strategy
- Chain of Responsibility
- Specification
- State
- Repository
- Unit of Work
- Observer / Publisher-Subscriber
- Memento
- Template Method

Do not force patterns where they do not improve the boundary.

## 3.3 Dependency inversion rule

High-level policy must depend on interfaces, not infrastructure.

Examples:

```text
UI -> Application interfaces
Application -> Domain interfaces
Infrastructure -> implements interfaces
Mazda SDK -> hidden behind adapter/gateway
Excel -> hidden behind projection interface
Database -> hidden behind repository interface
Scanner hardware -> hidden behind scanner adapter
```

## 3.4 Small-interface rule

Prefer multiple small interfaces over one giant interface.

Bad:

```python
class IFinanceSystem(Protocol):
    ...
```

Good:

```python
class IVendorResolver(Protocol):
    ...

class IExpenseRepository(Protocol):
    ...

class IJudgmentValidator(Protocol):
    ...
```

## 3.5 No shared implementation ownership

The agents may reference contracts owned by other agents, but they should not implement or redefine another agent's domain.

If a dependency is not yet available, create a placeholder reference in documentation and mark it as an external contract dependency.

## 3.6 Stable artifact rule

Each agent should produce:

```text
architecture/
    <agent-area>/
        README.md
        interfaces.py
        models.py
        enums.py
        types.ts       # only if needed
        CONTRACTS.md
```

If the codebase already has a preferred architecture location, use that instead.

Do not create duplicate architecture roots.

---

# 4. Agent 1 — Michiko
## Meaning: “the path”

### Role

Own the **application intake entry point**.

### GoF focus

- Facade
- Command
- Template Method

### Primary responsibility

Define the one application-facing interface that both scanner workflows use.

### Required contracts

Design interfaces/types for:

```text
IIntakeFacade
IIntakeWorkflow
ProcessScanCommand
IntakeResult
ResolutionStatus
```

Possible supporting models:

```text
IntakeId
ScannerId
DocumentId
WorkflowError
IntakeMetadata
```

### Required TypeScript boundary

If the browser calls this workflow, define the UI-facing request/result contract.

Example shape:

```ts
interface ProcessScanCommand {
    scannerId: string;
    scannerName: string;
    sourcePath: string;
    scannedAt: string;
}

interface IntakeResult {
    status: IntakeStatus;
    documentId?: string;
    message?: string;
}
```

### Must not design

- scanner hardware
- Mazda internals
- repositories
- reconciliation rules
- vendor/category logic

### Deliverable

A clean application boundary where:

```text
Scanner UI -> IIntakeFacade
```

and nothing in the UI needs to know whether Mazda was involved.

---

# 5. Agent 2 — Yui
## Meaning: “connection / binding”

### Role

Own the **scanner integration boundary**.

### GoF focus

- Adapter
- Bridge

### Primary responsibility

Define a common contract for:

- Freezer Scanner
- Window Scanner

while hiding their hardware/process differences.

### Required contracts

```text
IScannerAdapter
IScanEventSource
ScannedDocument
ScannerIdentity
ScannerCapability
ScanRequest
ScanResult
```

### Requirements

Both scanners must produce the same normalized `ScannedDocument` contract.

The scanner contract may contain:

```text
scanner_id
scanner_name
source_path
scanned_at
mime_type
page_count
device_metadata
```

### Must not design

- finance workflow
- Mazda calls
- vendor/category logic
- persistence
- report updates

### Deliverable

A hardware-agnostic scanner abstraction.

---

# 6. Agent 3 — Junko
## Meaning: “order / correctness”

### Role

Own the **deterministic intake pipeline contract**.

### GoF focus

- Chain of Responsibility
- Specification

### Primary responsibility

Define the ordered deterministic processing chain that runs before Mazda.

### Required contracts

```text
IDeterministicIntakePipeline
IIntakeRule
IRuleChain
RuleResult
Resolution
ResolutionStatus
IResolutionSpecification
```

### Recommended statuses

```text
CONTINUE
COMPLETE
NEEDS_JUDGMENT
HUMAN_REVIEW
REJECTED
```

### Rule contract requirements

Each rule should be independently testable.

A rule should not mutate global state.

Suggested conceptual shape:

```python
class IIntakeRule(Protocol):
    def evaluate(
        self,
        context: IntakeContext,
    ) -> RuleResult:
        ...
```

### Must not design

The actual rules.

Do not implement:

- vendor matching
- duplicate matching
- date rules
- check matching
- category rules

Those will plug into this chain later.

### Deliverable

The contract that allows deterministic rules to run in a stable order without one giant processor.

---

# 7. Agent 4 — Nao
## Meaning: “straight / honest”

### Role

Own **validation, invariants, and hard gates**.

### GoF focus

- Specification
- Composite

### Primary responsibility

Define the contracts that prevent Mazda or any other strategy from committing invalid finance state.

### Required contracts

```text
IResolutionValidator
IJudgmentValidator
IInvariant
IInvariantSet
ValidationResult
ValidationFailure
ValidationSeverity
```

### Expected invariant categories

The interface design should support future invariants for:

```text
vendor validity
category validity
date validity
amount precision
reporting period
duplicate prevention
check consistency
transfer consistency
source evidence consistency
projection consistency
```

### Important rule

Model confidence must not replace validation.

### Must not design

- actual invariant logic
- actual category list
- actual date rules
- actual validation messages beyond examples

### Deliverable

A deterministic validation contract that all Mazda proposals must pass.

---

# 8. Agent 5 — Tomoko
## Meaning: “knowledge / wisdom”

### Role

Own the **Mazda judgment boundary**.

### GoF focus

- Strategy
- Adapter

### Primary responsibility

Reduce Mazda to a narrow reasoning service.

### Required contracts

```text
IJudgmentStrategy
IMazdaJudgmentGateway
JudgmentRequest
JudgmentDecision
JudgmentTask
JudgmentConfidence
JudgmentEvidence
AllowedValueSet
```

### Suggested task enum

```text
CLASSIFY_DOCUMENT
RESOLVE_VENDOR
SELECT_CATEGORY
RESOLVE_POSSIBLE_DUPLICATE
RESOLVE_RECONCILIATION_CONFLICT
INTERPRET_UNUSUAL_RECEIPT
```

### Critical boundary

Mazda returns proposals.

Mazda does not:

- write database records
- update Excel
- rename files
- regenerate reports
- commit transactions
- perform arithmetic
- directly resolve workflow state

### Example response contract

```json
{
  "task": "resolve_vendor",
  "proposed_values": {
    "vendor_key": "cracker_barrel"
  },
  "confidence": 0.93,
  "reason": "..."
}
```

### Deliverable

A narrow adapter so the rest of the application is not coupled to Letta/Mazda APIs.

---

# 9. Agent 6 — Keiko
## Meaning: “order / rules”

### Role

Own the **document/vendor/category resolution contracts**.

### GoF focus

- Strategy
- Chain of Responsibility

### Primary responsibility

Define resolver interfaces for deterministic and semantic resolution.

### Required contracts

```text
IDocumentTypeResolver
IVendorResolver
ICategoryResolver
IResolutionStrategy
ResolutionCandidate
ResolutionEvidence
ResolverResult
ResolverPriority
```

### Intended future resolver chain

```text
Exact Key
→ Exact Alias
→ Known Source Mapping
→ Exact Historical Match
→ Deterministic Pattern
→ Mazda
→ Human
```

### Important rule

Do not implement any of those strategies now.

Only define the interface family that supports them.

### Deliverable

Composable resolver contracts that allow deterministic-first resolution.

---

# 10. Agent 7 — Ai
## Meaning: “affinity / matching”

### Role

Own the **matching and reconciliation contracts**.

### GoF focus

- Strategy
- Specification

### Primary responsibility

Define the interfaces for deterministic matching before Mazda sees ambiguous candidate sets.

### Required contracts

```text
IDuplicateDetector
ICheckMatcher
ITransferMatcher
ITransactionMatcher
IMatchStrategy
MatchResult
MatchStatus
MatchCandidate
MatchEvidence
MatchScore
```

### Expected future exact-match inputs

Support contracts capable of representing:

```text
account
amount
date
date window
check number
reference number
transaction direction
source identity
```

### Important rule

Separate:

```text
EXACT_MATCH
POSSIBLE_MATCH
NO_MATCH
AMBIGUOUS
```

Mazda should only receive the ambiguous/fuzzy side later.

### Deliverable

A reconciliation/matching contract family with no matching implementation.

---

# 11. Agent 8 — Riko
## Meaning: “logic / structure”

### Role

Own the **finance mutation boundary**.

### GoF focus

- Command
- Unit of Work
- Facade

### Primary responsibility

Define the one place where finance changes are requested.

### Required contracts

```text
IExpenseMutationService
ExpenseMutationCommand
AddExpenseCommand
EditExpenseCommand
DeleteExpenseCommand
AddTaxCommand
MoveExpensePeriodCommand
MutationResult
MutationStatus
MutationError
```

### Intended future responsibilities

A concrete implementation will eventually own:

```text
validate
→ update canonical record
→ synchronize persistence
→ update projections
→ recalculate totals
→ rename evidence
→ regenerate reports
```

But do not implement those steps now.

### Critical boundary

Mazda can propose/request a mutation.

Mazda cannot execute its internals.

### Deliverable

Command contracts for all supported finance mutations.

---

# 12. Agent 9 — Shiori
## Meaning: “guide / record”

### Role

Own **repositories and projections**.

### GoF focus

- Repository
- Unit of Work
- Observer / Publisher-Subscriber

### Primary responsibility

Define the boundary between canonical finance state and derived views.

### Required contracts

```text
IExpenseRepository
IVendorRepository
IDocumentRepository
ITransactionRepository
ITransferRepository
IUnitOfWork
IProjectionWriter
IExcelProjection
IReportProjection
IRecentReportProjection
ProjectionResult
RepositoryError
```

### Architectural target

```text
Canonical Finance Record
        │
        ├──> Excel Projection
        ├──> HTML Report Projection
        ├──> Recent Report Projection
        └──> UI View Model
```

### Important rule

Repositories own persistence contracts.

Projection interfaces own derived outputs.

Do not let Mazda or the UI become a persistence layer.

### Deliverable

A persistence/projection contract set with clear ownership.

---

# 13. Agent 10 — Kaori
## Meaning: “improvement / refinement”

### Role

Own the **self-improvement governance contracts**.

### GoF focus

- State
- Strategy
- Memento

### Primary responsibility

Define the interface architecture around:

```text
RUN
→ JUDGE
→ PROPOSE
→ EXPERIMENT
→ GATE
→ ACTIVATE
→ ROLLBACK
```

### Required contracts

```text
IImprovementWorkflow
IExperimentRunner
IActivationGate
IRollbackStrategy
IWorkflowStateMachine
ImprovementProposal
ExperimentResult
GateResult
ActivationResult
RollbackSnapshot
WorkflowState
```

### Important rule

The self-improvement system may propose semantic changes such as:

```text
vendor aliases
category heuristics
routing heuristics
prompt changes
matching heuristics
```

It must not own deterministic accounting mechanics such as:

```text
arithmetic
tax calculations
file naming
exact totals
database synchronization
Excel synchronization
date arithmetic
```

### Deliverable

A contract-only improvement workflow with explicit activation and rollback boundaries.

---

# 14. Shared Contract Ownership

To avoid 10 agents inventing overlapping models, assign ownership.

## Michiko owns

```text
ProcessScanCommand
IntakeResult
IntakeStatus
```

## Yui owns

```text
ScannedDocument
ScannerIdentity
```

## Junko owns

```text
Resolution
ResolutionStatus
RuleResult
```

## Nao owns

```text
ValidationResult
ValidationFailure
```

## Tomoko owns

```text
JudgmentRequest
JudgmentDecision
JudgmentTask
```

## Keiko owns

```text
ResolutionCandidate
ResolutionEvidence
```

## Ai owns

```text
MatchResult
MatchCandidate
MatchStatus
```

## Riko owns

```text
MutationCommand types
MutationResult
```

## Shiori owns

```text
Repository / Projection result types
```

## Kaori owns

```text
ImprovementProposal
ExperimentResult
WorkflowState
```

Other agents may import these types but should not redefine them.

---

# 15. Suggested Letta Agent Creation Template

Use one common agent template.

Each Letta agent should be created with:

```text
Name
Purpose
System Prompt
Working Directory / Scope
Allowed Outputs
Forbidden Outputs
Dependencies
Required Deliverables
Completion Criteria
```

---

# 16. Common System Prompt Prefix

Use this as the beginning of every architecture agent's system prompt:

```text
You are one of 10 parallel architecture agents designing the deterministic-first
Mazda finance system.

You are working in the architecture phase only.

Your job is to define interfaces, contracts, DTOs, enums, dependency rules,
and architecture documentation for your assigned responsibility.

Do NOT implement business logic.
Do NOT create concrete scanner, database, Excel, Mazda, matching, reporting,
or finance behavior.

Keep a GoF design-pattern mindset, but do not force patterns unnecessarily.

Prefer small interfaces, Dependency Inversion, explicit value objects,
clear ownership, and independently testable contracts.

Do not duplicate contracts owned by another agent.
If you require another agent's contract, import/reference it or document the
dependency.

The target runtime architecture is:

CODE -> unresolved -> MAZDA -> unresolved/invalid -> HUMAN

The scanner UI must never call Mazda directly.
Mazda returns structured proposals and must never directly commit finance state.
```

Append each agent's specialized section below that prefix.

---

# 17. Parallel Work Rules

The orchestrating agent should launch all 10 Letta agents after creating their isolated scopes.

Recommended isolation:

```text
architecture/michiko_intake/
architecture/yui_scanners/
architecture/junko_pipeline/
architecture/nao_validation/
architecture/tomoko_mazda/
architecture/keiko_resolution/
architecture/ai_matching/
architecture/riko_mutations/
architecture/shiori_persistence/
architecture/kaori_improvement/
```

If using separate git worktrees or sandboxes, one per agent is preferred.

Agents should not modify another agent's directory.

---

# 18. Integration Phase After All 10 Finish

Do not merge blindly.

Run one architecture integration pass.

The integration pass should check:

## Naming

Are names consistent?

Example conflicts to catch:

```text
IntakeStatus vs ResolutionStatus
DocumentId vs FinanceDocumentId
MatchCandidate vs ResolutionCandidate
```

## Ownership

Did two agents define the same DTO?

## Dependency direction

Reject dependencies such as:

```text
Domain -> UI
Domain -> Letta SDK
Repository -> UI
Scanner -> Excel
Mazda Gateway -> Database
```

## Cycles

Avoid:

```text
IntakeFacade -> MutationService -> IntakeFacade
```

## Boundary leaks

Reject Mazda-specific types outside the Mazda adapter boundary.

## Type consistency

Check:

- Python types
- TypeScript types
- enum values
- IDs
- datetime formats
- money/value object representation

---

# 19. Recommended Architecture Review Questions

After the 10 agents finish, ask:

1. Can the Freezer Scanner operate without knowing Mazda exists?
2. Can the Window Scanner operate without knowing Mazda exists?
3. Can `IIntakeFacade` be tested with a fake judgment strategy?
4. Can Mazda be swapped for a human strategy?
5. Can deterministic rules be added without editing the Facade?
6. Can vendor resolution strategies be reordered?
7. Can matching strategies be tested independently?
8. Can mutations occur without the UI knowing persistence details?
9. Can Excel/report projections be replaced without changing domain logic?
10. Can self-improvement be disabled without affecting normal intake?
11. Can Mazda return an invalid category without corrupting state?
12. Can a failed projection be detected without rerunning judgment?
13. Can a scanner implementation change without touching finance logic?
14. Can the application run a fully deterministic intake path with zero Mazda calls?

If the answer to any of these is "no," revisit the interface boundaries before implementation.

---

# 20. Definition of Done for Each Agent

Each architecture agent is finished only when it has produced:

- a short `README.md`
- interface declarations
- DTO/value-object declarations
- enums
- TypeScript interface declarations if applicable
- dependency notes
- explicit "owns / does not own" section
- zero business-logic implementations
- zero direct infrastructure logic
- no duplicated shared contracts
- no dependency inversion violations

---

# 21. Definition of Done for the 10-Agent Architecture Phase

The architecture phase is complete when:

```text
[ ] All 10 agent scopes exist.
[ ] All 10 agents completed contract-only work.
[ ] Shared types have a single owner.
[ ] No scanner UI depends on Mazda.
[ ] Mazda is behind IMazdaJudgmentGateway.
[ ] Deterministic pipeline is represented by interfaces.
[ ] Validation is represented by interfaces.
[ ] Resolver families are represented by interfaces.
[ ] Matching/reconciliation is represented by interfaces.
[ ] Finance mutations are represented by Commands/interfaces.
[ ] Persistence is represented by repositories.
[ ] Excel/reports are projections, not domain logic.
[ ] Self-improvement has explicit gates and rollback contracts.
[ ] Dependency directions have been reviewed.
[ ] No business logic has been implemented.
[ ] Architecture integration review passes.
```

Only after this review should implementation design begin.

---

# 22. Final Instruction to the On-Machine Agent

Build the **agents first**, not the finance implementation.

The purpose of these 10 Letta agents is to divide the architecture into independently understandable responsibilities.

Do not ask them to "build Mazda."

Ask them to build the **contracts that Mazda and deterministic code will later program against**.

The architecture should make this statement true:

> Mazda is replaceable.

The finance workflow should depend on:

```text
IJudgmentStrategy
```

not directly on:

```text
Mazda
Letta
a specific LLM
```

Likewise:

```text
scanner workflow depends on IScannerAdapter
persistence depends on repositories
reports depend on projections
mutations depend on Commands
deterministic routing depends on Resolution
```

This is the high-level architecture milestone.

Implementation starts only after these 10 contract sets are integrated and reviewed.
