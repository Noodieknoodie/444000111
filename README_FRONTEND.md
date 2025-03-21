# README_FRONTEND.md

//// TOP NAVIGATION ////
[HWM Logo]
- Payments (Home)
- Quarterly Summary
- Contacts
- Export Data
- Settings


//// PAYMENTS PAGE ////

//// SIDEBAR: CLIENT SELECTION ////
- Search Bar: Filters clients dynamically as user types.

- Client/Provider View Toggle (defaults to Client View):

Client View:
- Displays clients individually by name with initials/icon.
- Clearly but subtly indicates client status ("PAID"/"UNPAID") for the current period.
- Selecting a client refreshes the main page content accordingly.

Provider View:
- Displays providers, collapsed by default.
- Clicking a provider expands to reveal associated clients.
- Clients follow the same selection behavior and status indicators as in Client View.

//// MAIN PAGE: PAYMENT DETAILS ////

- Client Information:
  - Client Name (e.g., Belmont Cabinets)
  - Address (e.g., 187 109th Ave E, Seattle WA 98102)
  - Client Since (mm/dd/yyyy)
  - Participants (#)

- Contract Information:
  - Contract # (e.g., 12345)
  - Provider (e.g., John Hancock, Voya)
  - Payment Schedule: Monthly or Quarterly
  - Fee Structure: Percentage or Fixed
  - Annual Rate: 1.25% or $x,xxx if fixed
  - Period Rate: 0.1041% or $x,xxx if fixed  
(Note: Percentages under 1% use four decimals, above 1% use two.)

- Compliance Information:
  - Current Period: MMM YYYY (monthly) or Qx YYYY (quarterly)
  - Status: PAID or UNPAID
  - Last Payment:
    - Date (mm/dd/yyyy)
    - Applied Period: MMM YYYY or Qx YYYY
    - AUM: $x,xxx,xxx or "N/A"
    - Expected Fee: $x,xxx or "N/A"
    - Amount Received: $x,xxx
    - Variance: Clearly indicates "+$xx.xx Overpaid (x.xx%)", "-$xx.xx Underpaid (-x.xx%)", or "Within Target*" if within ±$3 of expected.
  - Missing Payments: Lists periods clearly (MMM YYYY or Qx YYYY).

//// PAYMENT ENTRY FORM ////

- Date Received: mm/dd/yyyy *(required)*
- Applied Period (Dropdown): Defaults to current collection period *(required)*
  - Split Payment Toggle:
    - Splits "Applied Period" dropdown into "Start" and "End" periods, defaulting both to current period.
- Amount: $x,xxx.xx *(required)*
- Assets Under Management: $x,xxx,xxx (gracefully handles if null)
- Expected Fee: Auto-calculates in real-time for percentage clients; fixed fee clients display their fixed rate clearly.
- Notes: Optional, unobtrusive text field summonable when needed.
- Add Attachment: Opens file explorer; attached filename clearly displayed with removable "[x]" option, similar to email attachment UX.
- Actions:
  - Submit: Checks for required fields; notifies user if missing.
  - Clear Form: Prompts confirmation if form has been modified.

EDIT MODE:
- Triggered from Payment History table actions.
- Clearly indicates focus state and stylistic adjustments.
- Form pre-populates with selected payment details.
- "Clear Form" button changes to "Cancel Edit"; prompts confirmation if edits have occurred.

//// PAYMENT HISTORY TABLE ////

Columns:
- Payment Date
- Period
- AUM
- Expected Fee
- Amount Received
- Variance: Clearly indicated as "+/- $xx.xx" with visual cues for overpayment/underpayment.
- Actions: [View Attachment (conditionally visible), Edit, Delete]

Handling Split Payments:
- Displays total payment clearly on the main row, collapsible (collapsed by default).
- Expanded view shows individual payments within clearly.
- Muted display for AUM, Expected Fee, Variance on collapsed rows for clarity.

//// DOCUMENT VIEWER SPLIT-SCREEN ////

- Purpose: To efficiently view scanned documents (checks, payments, attachments) alongside payment details for quick manual verification.
- Triggered when selecting the "View Attachment" action from a payment in the Payment History table.
- Viewer slides in smoothly from the right, splitting the page clearly into a 60% (main page) / 40% (document viewer) layout.
- When active, the client navigation sidebar automatically hides to maximize screen space.
- Document viewer remains fixed ("sticky")—it does not scroll with the main content area.
- Supports PDFs, PNGs, JPGs, and JPEGs with zoom capabilities for detailed inspection.
- Allows independent scrolling within the document viewer for multi-page files, functioning similarly to a standalone PDF viewer.
- While open, the main payment page adjusts intelligently: non-essential details (last payment summaries, action buttons, or irrelevant page elements) temporarily hide, ensuring clear focus on essential information.
- A clearly visible "Close" button exits the viewer and restores the original layout, including the return of the client navigation sidebar.
- All elements and transitions are precisely coordinated to maintain seamless interaction and usability.
