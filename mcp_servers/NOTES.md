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

`clinic_client.py` (#114) plays the part of the three agents' MCP clients. It runs the booking,
pharmacy and reports demos together with `asyncio.gather`, so their lines can interleave; each line
starts with its server name. It then ends with the diagram's example flow on its own: add a new
medicine, then view the inventory.

### Booking

The Booking MCP Server provides tools to register patients and book appointments.
Before booking, it checks whether the patient exists and whether the doctor already has an appointment at the same date and time.
If the doctor is already booked, the tool returns an error to prevent double booking.

### Pharmacy

add_inventory only returns the one row it changed, for example {'medicine': 'Amoxicillin', 'stock': 30}. That shows the call worked, but not that the medicine is now part of the shared inventory. So the new-medicine flow ends with view_inventory, which reads the whole inventory back from the server and shows Amoxicillin sitting next to the other medicines.

### Medical Reports

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
