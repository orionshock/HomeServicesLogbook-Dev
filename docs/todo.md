# Home Services Logbook TODO

## Global UX
- [ ] Warn before navigating away when there are unsaved edits in vendor details or entries.
- [ ] Improve form validation feedback (clear errors, inline guidance, and recovery hints).

## Entries
### Log History Behavior
- [ ] While editing an entry, hide that same entry from the history list.
- [ ] Update each history card to use title as the primary line and created timestamp as subtitle.
- [ ] Show only the 10 most recent entries. With a more button?
- [ ] Make history panel scrollable and anchor it near the notes section bottom-right.
- [ ] Let history panel grow when note body textarea expands, but only until scrolling is no longer needed.
- [ ] Prevent awkward empty space in history panel if the note box becomes very tall.
- [ ] Replace text "Edit" link with a pencil icon button (common edit affordance).
- [ ] Add entry labels with both:
  - [ ] Free-form label input.
  - [ ] Previously used label suggestions.

## Vendors
- [ ] Consider renaming vendor categories to labels in the database model.
- [ ] Re-implement vendor categorization as:
  - [ ] Free-form input.
  - [ ] Previously used suggestions.

## Label System
- [ ] Keep labels and categorization unified conceptually on the backend.
- [ ] Treat vendor classification as "categories" and entry classification as "labels" in UI language.
- [ ] Plan for labels/categories to become searchable fields.
- [ ] Decide whether to add a dedicated labels table (preferred if needed), even though avoiding a new table is preferred initially.

## Settings
### Browser-Local Settings
- [ ] Always show archived toggle.
- [ ] Timezone and timestamp display preferences:
  - [ ] Browser-derived timezone vs explicit timezone.
  - [ ] Long absolute format.
  - [ ] Short absolute format.
  - [ ] Relative format.
- [ ] Theme support (future).

### Server-Side Settings / DB Management (Open Questions)
- [ ] Should some settings be server-side instead of browser-local?
- [ ] Label management and color settings.
- [ ] Import / Export / Reset / Delete actions scoped by:
  - [ ] Entire database.
  - [ ] Vendor.
  - [ ] Timeframe.
  - [ ] Label.
