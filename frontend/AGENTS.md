# Frontend UI conventions

Use `src/components/Select.jsx` for all dropdowns. Pass value/onChange props and option children; retain associated labels. The shared control renders themed options and supports keyboard navigation. Shared geometry, arrow placement, and padding belong in `src/components/Select.css`. Do not duplicate dropdown wrappers, arrows, or padding rules per view. Keep status colors in theme styles and use layout-only width overrides when needed. Verify light/dark themes and keyboard interaction when changing shared controls.

Do not add explanatory descriptions or helper paragraphs to sections unless the user explicitly requests them and provides the wording. Keep necessary field labels, validation errors, and save status messages. Start development servers only in PyCharm's Backend Server and Frontend Server terminal tabs, not background agent terminals.
