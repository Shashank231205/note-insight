# Prompt Conventions

Every prompt in `backend/src/agent/prompts/` follows one structure. A test
(`tests/unit/test_prompt_registry.py`) asserts the required sections are
present, so the convention is enforced rather than merely documented.

## The required structure

```
[ROLE & CONSTRAINTS]   who the model is, and the boundary of its authority
[INSTRUCTIONS]         numbered: parse -> verify -> execute -> return
[DON'TS]               explicit prohibitions, each one a failure we have seen or expect
[OUTPUT FORMAT]        the exact contract
[EXAMPLES]             at least one worked input -> output pair
{note_content}         the placeholder the registry substitutes
```

## Why this structure

**Role before task.** Stating the role and its limits first is what makes "you do not have authority to practise medicine" a constraint on everything that follows, rather than a caveat the model reads after it has already decided what to do.

**Prohibitions get their own section.** A "don't" buried inside an instruction competes with the instruction. Listed separately, each prohibition is a checkable rule, and each one in our prompt corresponds to a real failure mode: fabricated quotes, inferred diagnoses, family history counted as active, markdown fences around JSON.

**Examples carry the edge case, not the happy path.** The worked example in `v1` is chosen because it contains a family-history mention that must *not* appear in the output. An example that only shows the obvious case teaches nothing the schema had not already said.

## The one deviation from the source template, and why

The general template specifies a prose output format:

```
1. Status: [SUCCESS / ACTION REQUIRED / OUT OF SCOPE]
2. Summary: ...
3. Details: ...
4. Next Steps: ...
```

Note Insight cannot use a prose format. The whole pipeline depends on structured output — `response_mime_type=application/json` plus a `response_schema`, validated by Pydantic before anything reaches the database. Prose would have to be parsed, and the specification marks down free-form text parsed with regex or string splitting.

So the template's four output elements are preserved, mapped onto the JSON contract:

| Template element | Note Insight field | Why it maps |
|---|---|---|
| Status | `conditions[].documentation_status` | The per-condition verdict is the real status; a single document-level status would flatten a note that has one well-documented and one ambiguous condition |
| Summary | `summary` | Direct |
| Details | `conditions[]` with `evidence_quote` | The technical detail, each item carrying its own evidence |
| Next Steps | `documentation_gaps[]` | Already specified as specific and actionable |

The template's intent — a fixed set of sections, no conversational fluff, itemized actions — is honoured. Only the serialization differs, and it differs because a machine consumes this output rather than a person.

## Rules for adding a prompt

1. New file `vN_<purpose>.md` in `agent/prompts/`, registered in `registry.py`.
2. Never edit a shipped prompt in place. `prompt_version` is stored on every analysis and forms part of the cache key; editing v1 silently changes what historical rows mean.
3. Bumping the version invalidates the cache for that prompt, which is the intended behaviour — re-analysing under a new prompt should produce a new analysis, and the old one survives for comparison.
4. Iterate against saved real responses replayed through the validator, not against the live API. Prompt iteration is the easiest way to burn free-tier quota for no benefit.
