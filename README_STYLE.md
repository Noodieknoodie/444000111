🎨 New Design Theme: "Refined Operator"
A UI theme designed for real users who make high-value decisions. It’s calm under pressure, never in your way, and styled like software you’d trust with millions — because you do.

✅ Color System:
Base: Deep graphite / slate surfaces — easy on the eyes, not black but not too soft.
Accent: A strong, smart hue like midnight blue, slate teal, or burnt orange. Just enough to guide the eye.
Text: Off-white and soft gray typography.
Borders/Lines: Ultra-thin 1px soft separators — less chrome, more focus.
States:

Success = Cool green (not neon)
Warning = Soft amber
Error = Desaturated red
Focus = Steel blue glow
🎯 Optional Accent Color Examples:

#2563EB (Indigo 600) for links + active elements
#10B981 (Emerald) for confirmations
#F97316 (Orange 500) for subtle highlights or "due soon"
#F43F5E (Rose 500) for errors, missing data
✍️ Typography
Primary Font: Inter or General Sans – modern, ultra-legible, feels professional

Headers: 600–700 weight
Body: 400–500 weight
Data Fields: Monospaced or tabular-aligned styles (consider IBM Plex Mono for subtle tech elegance)
Hierarchy should be driven by size + spacing, not color or weight abuse.

🧱 Layout & Structure
Single-page dashboard, no scroll unless truly needed. Think "everything I need is visible or one click away."

Smart nesting: Cards inside cards? Nope. Use layers, hover reveals, and inline expanders
Visual grouping: Thin border dividers, grouped shadows, or slight background elevation (2dp max)
Dense but breathable — give fields space, but don’t waste vertical real estate
Sticky elements where helpful (e.g., client header, action bar for payments)
🪄 Microinteractions & Motion
Hover states = soft shadow lifts or glow edge
Button interactions = magnetic pull, quick tactile press down
Field focus = animated underline or ring, never full box glow
Payment history rows: animate in on change, slide in left on add, fade on delete
Transitions: quick and elegant — never more than 300ms, never "bouncy"
🎛 Component Behavior Suggestions
Sidebar

Active client glows with left border or underglow
Quick search or filter option at top
Optional pin/favorite toggle per client
Top Client Header

Subtle client logo or initials badge (e.g., in circle or square avatar)
Animates on change with slide & fade
Includes current contract status badge: “Up to date” / “Overdue” / “Missing Periods”
Add Payment Panel

Docked right or slide-in panel from bottom
Highlights auto-calc fields subtly on hover
Expected Fee shows formula breakdown inline (click-to-expand)
Payment Table

High-density layout but spaced cleanly
Variance column: green for under, red for over — color-coded pill indicators
Attachments: preview as file icon + name or image thumbnail
Inline edit = double-click to unlock, confirm on enter or blur
Pagination optional; year tabs or collapsible year sections preferred
🔐 UX Mental Model
This isn’t a consumer SaaS — this is your cockpit. It should feel like:

A control panel
A command interface, not a landing page
Something you never dread opening — fast, precise, tailored to how you think
Think Linear, Arc Browser, Cron, Superhuman — built for operators, not casuals.

