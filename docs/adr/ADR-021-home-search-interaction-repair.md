# Homepage Search interaction repair

Server evidence 2026-09-08: IP port80 and frontend port3000 return identical HTML. Live standalone image is 9f082e7-leisure, build H201mo0cEFS4jGxRiDVT7; source current is ac379c1 with no bind mount. Editing source or building the unrelated port3210 instance does not update the IP.

Chrome on the actual IP at1440/768/430/390: fs-scrim intercepts the first origin-to-destination click; at768 the date panel overflows the viewport; at430/390 the fixed bottom navigation obscures confirmation. Search submits to the homepage although the current owner requires the existing /search/results route.

Decision: remove blocking scrim and use pointer-outside dismissal; show small-screen pickers in the form flow with scroll clearance. Preserve existing colors, typography, imagery, tabs and backend architecture. Validate criteria, carry selected dates and the full passenger count to the existing Search API, use the existing results page. No seeds, providers, auth or payments.

Acceptance: real browser interaction at all four widths, autocomplete selection, editable dates and passengers, one valid public Search request, correct URL and rendered response, no console/network errors, before/after screenshots. An honest zero-result response is distinguished from confirmed live inventory. Build and candidate checks precede swapping production; retain the prior container for rollback.

Rollback checkpoint: /home/ubuntu/karen-audit-20260908-search/source-before.tar.gz and before.json.
