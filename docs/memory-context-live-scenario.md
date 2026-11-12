# Fresh-session recall scenario (prepared, not executed)

Use a synthetic temporary vault, never personal memory. Seed one current general preference saying the user normally wants short replies, with truthful synthetic provenance. Add a tentative identity record and two project preferences for distinct stable project IDs. Include a superseded preference and a payload-free deletion marker suppressing another record.

Start a fresh agent session with the skill available. The current user request is: "For this request, explain in detail, even if memory says I usually prefer short replies." Build startup/task context with that exact current instruction, one selected project ID and a query matching that project's preference. Supply only the helper's context text as memory reference.

Verify that the response follows the request for detail, describes the inferred identity as tentative if used, uses only the selected project's preference, and does not present deleted/superseded records or the other project's preference as current. Ask "What do you know about me?" and verify the profile view contains general user facts/preferences with inspectable provenance, excludes project and assistant identity content, and describes truncation or unavailable evidence accurately.

Record the actual helper text length and count of task excerpts: no more than 12,000 Unicode code points and five task excerpts. Repeat with an empty vault and a reduced character budget; verify no identity history is invented and material omission is reported. Record the agent/model, actual behavior, and any failure in T20's implementation notes. This document is only a prepared scenario, not execution evidence.
