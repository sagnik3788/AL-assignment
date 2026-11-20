# Demonstration walkthrough

Target length: 3–4 minutes. Use non-sensitive sample material.

1. Open the Margin research desk and point out the distinct source-library layout and the empty-state prompt.
2. Upload `sample-documents/course-guide.txt`; show the passage count and source appears in the sidebar.
3. Ask “What is the field report due date?” The answer should cite the source. Follow up with “Why might there be a different date?” to show conversational query context and the dated addendum/calendar conflict.
4. Upload `sample-documents/field-study.txt`; ask which site had the highest mean nitrate and request the value. Show that a source page reference appears.
5. Ask for a student's home address. If retrieval score is below threshold, show the deterministic abstention. If scores are high for unrelated text, explain that this is an evaluation case for model abstention and inspect the report.
6. Remove a source, then refresh the page to show the library state persists. Use **New desk** to show session isolation.
7. Briefly show `/api/docs`, the architecture diagram, and the live evaluation command/report status.

Do not present the pending live retrieval metrics as completed results. Run the live evaluation with the deployment key before recording any quality claim.
