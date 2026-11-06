"""Konvey as an engine for coding harnesses (MCP server and run plumbing).

The package is intentionally thin: it imports the existing stage and render modules and
adds what a harness needs around them — a run directory, per-beat preview stills, and
detached jobs for the slow operations. It does not import the Konvey agents.
"""
