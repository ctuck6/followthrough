# Frontend UI conventions

Use `src/components/Select.jsx` for all dropdowns. Pass normal native select props and option children; retain associated labels. Shared geometry, arrow placement, and padding belong in `src/components/Select.css`. Do not duplicate dropdown wrappers, arrows, or padding rules per view. Keep status colors in theme styles and use layout-only width overrides when needed. Verify light/dark themes and keyboard interaction when changing shared controls.
