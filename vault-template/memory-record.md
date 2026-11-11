# Memory record template

Create a record using the version 1 contract. Generate a new UUID and replace
each value with the actual evidence and scope. This template is guidance, not
itself a valid memory record. Do not include project filesystem paths.

```markdown
---
schema_version: 1
id: "UUID-v4"
kind: "user_fact"
title: "Title"
scope: "general"
basis: "user-stated"
state: "current"
created_at: "YYYY-MM-DDTHH:MM:SSZ"
updated_at: "YYYY-MM-DDTHH:MM:SSZ"
sources: ["Available conversation context or source URL"]
related_ids: []
supersedes: []
---
Concise memory content.
```

For project scope add `project_id: "UUID-v4"`; a project record uses its own
ID. Choose the appropriate kind, basis, and state from the contract.
