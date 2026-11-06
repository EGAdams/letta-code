"""Manual, human-run operator scripts -- never imported by the dashboard
server itself. Each one does something (provisioning a Bridge client,
rotating a token) that needs real entropy or file-system authority outside
what an agent should do unattended."""
