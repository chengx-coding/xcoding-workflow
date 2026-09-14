# Legacy Migration

`scan-legacy` is read-only. It inspects only the canonical generic delegated-Agent definition and public `skills/xc-*/SKILL.md` contracts below the supplied source root. It reports relative paths, marker IDs, and line numbers. It does not return prompt text, read another Skill's private references or worker assets, create profiles, infer capabilities, or mutate source.

For every candidate, the owner explicitly reviews role instructions, declared context, required versus optional capabilities, output paths, failure behavior, and host evidence. The owner then authors and validates its own profile. A failed profile validation or preparation stays failed; it never resumes through the legacy prompt path.

No generic sunset date is defined. Existing nodes without a v1 profile may continue through the explicit `legacy-prompt` route while owners migrate them. Receipts and runtime history are not rewritten during migration or rollback.
