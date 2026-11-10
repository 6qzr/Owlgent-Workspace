# Clinic MCP servers: notes

Practice task from the trainer's issue (CodelineAtyab/CodelineLegendsAIWorkflows#276), tracked here
in #109. Data lives in memory; there is no database and no LLM.

## What is an MCP server? What is a tool?

An MCP server is a small program that offers a list of actions over the Model Context Protocol, so
any MCP client (later, an agent) can discover and call them in the same way. A tool is one of those
actions: a normal Python function registered on the server. Its name, type hints and docstring
become the tool's name, input schema and description, and that is all a client sees before it
calls it. The client connects, lists the tools, then calls one by name with arguments and gets the
returned value back.

## Which part of the Clinic diagram did we build?

| Server | Port | Tools | Owner |
|---|---|---|---|
| Booking | 8001 | `register_patient`, `book_appointment` | #111 |
| Pharmacy | 8002 | `view_inventory`, `add_inventory` | #112 |
| Medical Reports | 8003 | `get_patient_medical_records`, `get_opd_records` | #113 |

`clinic_client.py` (#114) plays the part of the three agents' MCP clients and ends with the
diagram's example flow: add a new medicine, then view the inventory.

### Booking

### Pharmacy

### Medical Reports

Both tools check that the patient ID exists before reading any records. For an unknown patient
they return an error dict instead of raising an exception: an unknown ID is an expected case, so
the tool call still completes normally and the client gets a predictable answer it can inspect.

## What we skipped

The agents themselves, the UI, the API gateway, auth (JWT/RBAC), Temporal, Redis, PostgreSQL,
Qdrant and monitoring. They are outside this task, so each server keeps its data in plain dicts
and lists.

## How to run

From `mcp_servers/`, one terminal each:

```bash
uv run hello_server.py      # warm-up on 8004; then: uv run hello_client.py  -> 5
uv run booking_server.py    # port 8001
uv run pharmacy_server.py   # port 8002
uv run reports_server.py    # port 8003
uv run clinic_client.py     # a fourth terminal, once the three servers are up
```

Restarting a server resets its data, because it is only kept in memory.
