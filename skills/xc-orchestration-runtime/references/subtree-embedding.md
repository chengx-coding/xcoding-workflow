# Subtree Embedding

Use embedded subtrees when a runtime node needs to invoke another workflow template as part of the same scheduling tree.

```powershell
python "$SKILL_DIR/scripts/orchestration.py" embed-subtree `
  --tree <parent_tree_ref> `
  --parent <parent_node_id> `
  --template <managed_child_template> `
  --instance-id <child_instance>
```

## Preconditions

- The parent must be a `composite` or `loop` runtime node.
- The child must be a valid, checksummed managed template.
- `instance-id` is optional; when supplied it must be lowercase kebab-case and unique within the parent runtime tree.

## Runtime Behavior

The runtime validates the child template, instantiates it with an isolated instance namespace, rewrites all `local:` references, and records a `meta.template_instances.instance` entry.

Child runtime IDs follow:

```text
rt_<parent-run-id>__<child-instance-id>__<child-template-id>
```

This preserves the original template ID and the embedding instance ID on every runtime node, so the viewer and operators can trace status back to its source template.

## Blackboard and Artifacts

Embedding only composes node structure. The parent runtime blackboard remains the shared control plane. Child template defaults are not copied into the runtime blackboard; set explicit shared values before or after embedding.

Child tasks should use artifact paths isolated by instance:

```text
<artifact-root>/<child-instance-id>/<child-template-id>/
```

The current implementation does not provide linked child runs, blackboard scope translation, artifact indexing, or cross-process cancellation.
