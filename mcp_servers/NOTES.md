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

The Medical Reports MCP server provides access to patients' medical history and outpatient department (OPD) records.

- **Port:** 8003
- **Server file:** `reports_server.py`
- **Client file:** `reports_client.py`

#### Available tools

| Tool | Input | Description |
|---|---|---|
| `get_patient_medical_records` | `patient_id: int` | Retrieves a patient's medical records, including date, diagnosis, and notes. |
| `get_opd_records` | `patient_id: int` | Retrieves a patient's outpatient records, including visit date and department. |

#### Error handling

Both tools check whether the requested patient ID exists before retrieving records. If the patient is not found, they return an error dictionary instead of raising an exception.

Returning an error dictionary provides a predictable response that the client can inspect and handle. It also allows the MCP tool call to complete normally rather than failing with an exception for an expected situation, such as an unknown patient ID.

#### Testing

Run the server:

```bash
uv run reports_server.py
```

In another terminal, run the client:

```bash
uv run python reports_client.py
```

The client lists the available tools, retrieves medical and OPD records for a known patient, and tests error handling using an unknown patient ID.


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
