One tiny change: the raccoon support queue needs search. Extend the existing /app/index.html and preserve its visual design and all existing behavior.

Add a text input with the exact accessible label "Ticket search". Update visible tickets as the user types. Match a case-insensitive substring of the ticket TITLE only, trim leading/trailing query spaces, and combine search with the existing status filter. An empty query shows all tickets allowed by the status filter. A query with no matches shows no visible ticket elements. Keep the layout usable at 390px width.

The existing app contract still applies:

Build a small, polished browser app for a help desk staffed entirely by raccoons.
The company motto is "We take your tickets. And occasionally your lunch."

Write the finished app to /app/index.html. Use one self-contained HTML file with
inline CSS and JavaScript. No build step, backend, external libraries, fonts,
images, or network requests. The app will be served over HTTP by the evaluator.

Required behavior and accessible controls:
1. Show a level-one heading named "Raccoon Help Desk".
2. Provide a text input with an associated visible label "Ticket title".
3. Provide a select labeled "Priority" with options Low, Normal, and Urgent.
4. Provide a button named "Create ticket". Creating a ticket shows its title,
   priority, and initial status Open. Render each ticket in an element with
   data-testid="ticket" so automated checks can identify it.
5. Reject an empty or whitespace-only title. Show "Enter a ticket title." and
   create no ticket. Avoid native required-field validation hiding this message.
6. Each open ticket has a button named "Resolve". Clicking it changes that
   ticket's visible status to Resolved without changing other tickets.
7. Provide a select labeled "Status filter" with options All, Open, and Resolved.
   The selection controls which tickets are visible, including an empty state.
8. Store ticket titles, priorities, and statuses in localStorage. All must survive
   a page reload. New browser contexts should start with no tickets.
9. Render titles as plain text, even if they contain HTML-like text.
10. At a viewport width of 390 pixels, the document must not scroll horizontally,
    even with a long unbroken ticket title. Keep controls usable on mobile.

Make the interface clear and attractive on a conference screen. Raccoon-themed
copy is encouraged, but preserve the exact control labels above. Visual taste
will be voted on separately; automated scoring covers the stated behavior.

Use the eight-minute task limit to implement and check your work. The only
submitted file is /app/index.html. Do not write grader reports or reward files.

Work only in /app. Do not invoke another AI agent, model, or external service. Do not read or modify credentials or runner logs. Use only the provided environment. Leave the finished app at /app/index.html. You have eight minutes; finish as soon as the requirements work.
