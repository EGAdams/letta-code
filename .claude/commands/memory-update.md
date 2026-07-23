---

description: Preserve newly discovered project knowledge for future Claude instances
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git status:*), Bash(git diff:*)
----------------------------------------------------------------------------------

Review the work completed and information discovered during this session. Preserve any new, verified project knowledge that would help future Claude instances understand and work on this project without rediscovering the same information.

## Information to preserve

Look for newly discovered information involving:

* Project structure and important directories
* Application architecture and component relationships
* Installation, build, startup, and deployment procedures
* Development and testing workflows
* Debugging and troubleshooting procedures
* IP addresses, ports, hosts, containers, APIs, and service locations
* Configuration files and required environment variables
* Report, log, output, and generated-file locations
* Important tooling, scripts, commands, and utilities
* Known problems, their causes, and verified fixes
* Important design decisions or project conventions
* Incomplete work, risks, dependencies, and recommended next steps
* Anything else that could save a future agent time

## Documentation procedure

1. Inspect the current conversation, files examined, commands executed, changes made, and problems solved.

2. Locate the project's existing persistent documentation, including files such as:

   * `CLAUDE.md`
   * Existing project-status or handoff documents
   * README files
   * Files under `docs/`
   * Development notes or troubleshooting guides

3. Update the most appropriate existing document whenever possible.

4. Keep `CLAUDE.md` concise. Store only essential information that should always be available to future Claude instances.

5. Put lengthy procedures, troubleshooting details, histories, or reference material in an appropriate supporting document. Add a concise reference to that document from `CLAUDE.md` when necessary.

6. If no suitable persistent documentation exists:

   * Create `docs/PROJECT_KNOWLEDGE.md`.
   * Create or update the root `CLAUDE.md` with a brief reference to it.

7. Merge new information into existing sections instead of repeatedly appending duplicate notes.

8. Reconcile conflicting information carefully. Replace outdated information only when the newer information has been verified. Clearly mark uncertain or potentially outdated information.

## Rules

* Preserve only project-specific information that is new and useful.
* Verify paths, ports, commands, filenames, and procedures before recording them.
* Do not invent missing details.
* Do not save passwords, API keys, access tokens, private keys, session cookies, or other secrets.
* Do not modify application source code while running this command.
* Keep documentation organized, concise, and actionable.
* Include exact commands and paths when they are important and verified.
* Explain known problems using this structure when practical:

  * Symptom
  * Cause
  * Fix
  * Verification
* If no meaningful new information was discovered, do not modify any files.

Afterward, report:

* Which documentation files were created or updated
* A concise summary of the knowledge preserved
* Any information that could not be verified
* Whether no documentation changes were necessary
