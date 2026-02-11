---
name: todo
description: "Curate a data/todo.md that keeps track of things I have to do, things that we tackle ... and give me some suggestions about how to best unpile the list."
---

# Todo Skill

You are helping the user manage their personal todo list stored in `data/todo.md`. This is a lightweight, markdown-based task tracker for keeping track of work items, ideas, and priorities.

## File Location

The todo list lives at `data/todo.md`. Always read it before any operation.

## Commands

### Show the list: `/todo` or `/todo show`

1. Read `data/todo.md`
2. Display a clean summary: count of open items, grouped by section
3. If there are 5+ open items, offer a brief triage suggestion (see Triage below)

### Add an item: `/todo add <description>`

1. Read `data/todo.md`
2. Append the new item to the **Inbox** section with today's date
3. Format: `- [ ] <description> *(added YYYY-MM-DD)*`
4. Save the file

### Complete an item: `/todo done <description or number>`

1. Read `data/todo.md`
2. Find the matching item (fuzzy match on description, or by position)
3. Change `- [ ]` to `- [x]`
4. Add completion date: `*(done YYYY-MM-DD)*`
5. Save the file

### Remove an item: `/todo remove <description or number>`

1. Read `data/todo.md`
2. Find and remove the matching item entirely
3. Save the file

### Move an item between sections: `/todo move <item> to <section>`

1. Read `data/todo.md`
2. Remove item from current section, add to target section
3. Save the file

### Triage / Prioritize: `/todo triage`

1. Read `data/todo.md`
2. Analyze all open items
3. Provide actionable suggestions:
   - **Quick wins**: Items that seem small and could be knocked out fast
   - **Blockers**: Items that other things might depend on
   - **Stale**: Items sitting in Inbox for 7+ days without being moved to a section
   - **Groupable**: Items that could be batched together
   - **Deprioritize**: Items that could be dropped or deferred
4. Offer to reorganize the file based on the triage

### Clean up completed items: `/todo clean`

1. Read `data/todo.md`
2. Move all `[x]` items to an **Archive** section at the bottom
3. Save the file

## File Format

```markdown
# Todo

## Inbox
_New items land here. Move them to a section when you're ready._

- [ ] Something to do *(added 2025-02-11)*

## In Progress
_Things actively being worked on._

## Blocked
_Waiting on something or someone._

- [ ] Blocked item *(added 2025-02-10)* -- waiting on X

## Archive
_Completed items._

- [x] Done thing *(added 2025-02-08, done 2025-02-11)*
```

### Sections

The default sections are **Inbox**, **In Progress**, **Blocked**, and **Archive**. The user can add custom sections and the skill should respect them. New items always go to Inbox unless the user specifies otherwise.

### Item Format

- Open: `- [ ] Description *(added YYYY-MM-DD)*`
- Open with note: `- [ ] Description *(added YYYY-MM-DD)* -- note text`
- Completed: `- [x] Description *(added YYYY-MM-DD, done YYYY-MM-DD)*`

## Triage Logic

When triaging, think about:

1. **Age**: Items in Inbox for 7+ days need attention - either promote them or drop them
2. **Size**: Can you tell if something is a quick 5-minute task vs. a multi-day effort? Call out quick wins
3. **Dependencies**: Do any items seem related or sequential? Suggest ordering
4. **Batching**: Can items be grouped by theme (e.g., "these 3 are all about docs")
5. **Staleness**: Anything that's been sitting untouched for 2+ weeks should be questioned - is it still relevant?
6. **Load**: If there are 10+ open items, suggest the user pick their top 3 for the day/week

## Behavior Guidelines

- **Lightweight**: This is a personal scratchpad, not Jira. Keep operations fast and simple
- **Non-destructive**: Never delete items without being asked. Use Archive for completed items
- **Date-aware**: Always stamp items with dates so staleness tracking works
- **Context-aware**: When adding items during a conversation (e.g., user says "remind me to follow up on X"), add them naturally
- **Conversational**: When showing the list, don't just dump markdown - summarize and highlight what matters
- **Proactive triage**: When showing a list with 5+ items, briefly note if anything looks stale or quick-winnable

## Example Sessions

**User:** `/todo`
**You:** Read todo.md, show summary like:
> You have **7 open items**: 3 in Inbox, 2 In Progress, 2 Blocked.
>
> Heads up: "Update API docs" has been in Inbox for 12 days. Worth promoting or dropping?
> Quick win: "Fix typo in README" looks like a 2-minute job.

**User:** `/todo add review Q1 planning doc`
**You:** Add to Inbox with today's date, confirm:
> Added "review Q1 planning doc" to Inbox.

**User:** `/todo done fix typo`
**You:** Find the matching item, mark complete:
> Marked "Fix typo in README" as done.

**User:** `/todo triage`
**You:** Full analysis with grouping, quick wins, stale items, and recommendations.
