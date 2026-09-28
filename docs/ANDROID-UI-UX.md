# Mozart Android UI / UX Contract

## Goal

Mozart is a live musical instrument, not a form-driven utility. The Android UI must expose performance controls quickly on a landscape phone while leaving room for future controls.

## Layout rules

- Landscape is the primary orientation.
- Never build the main screen as one unbounded vertical list of full-width controls.
- Group controls by musical responsibility: musical context, Link/transport, accompaniment/performance, pattern shaping, macros, MIDI I/O, and experimental/debug tools.
- Use a compact two-column control surface on landscape displays when practical.
- The main content must live inside a vertical ScrollView (or an equivalent safe container) so new controls can never become unreachable.
- Keep fixed chrome minimal: title/status header plus a small event/status strip.
- Prefer rows of related controls over one giant button per feature.
- Keep section labels visually distinct from controls and status text.
- Reserve visible breathing room for future additions; do not pack controls edge-to-edge.

## Control sizing

- Target approximately 36–42dp control height for the main performance buttons.
- Do not use default Android button minimum sizing without explicitly constraining it.
- Keep text compact (roughly 10–12sp for dense performance controls).
- Remove oversized internal padding when the stock Android Button would consume excessive vertical space.
- Maintain a usable touch target; compact does not mean tiny.
- Long diagnostic strings must not be allowed to expand the layout indefinitely.

## Visual hierarchy

Use a restrained dark instrument-oriented palette with one primary accent and one warning/stop treatment.

Hierarchy:
1. Current Link/key state.
2. Start/stop and MIDI connection state.
3. Accompaniment role.
4. Live pattern/performance controls.
5. MIDI input and experimental/debug controls.

Controls that affect musical continuity should communicate their quantized nature in the event/status message rather than by expanding the control itself.

## Status and diagnostics

- The status area is compact and bounded.
- Keep only the latest one or two user-facing status messages visible.
- Detailed diagnostic information belongs in dedicated status labels or debug tools, not in a growing TextView.
- Connection state should be visible without pushing primary controls off-screen.

## Regression gate

Before declaring an Android UI build usable, verify on a real landscape phone that:

- the app opens without clipped essential controls;
- START, STOP, TEST MIDI OUT, KEY, SCALE, KEY SOURCE and the main accompaniment controls are reachable without hunting;
- the screen can scroll when content exceeds the viewport;
- no button becomes taller simply because its label is long;
- adding another section does not make existing controls inaccessible;
- landscape remains the primary, intentional composition.

