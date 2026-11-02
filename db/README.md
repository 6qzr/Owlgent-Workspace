# Database scripts

Every `*.sql` file here runs automatically, in name order, the **first** time the `db`
container starts (empty volume). CI applies the same files before running tests.

Naming: `NNN_<what>.sql`. For example, `001_schema.sql` holds all tables agreed at the architecture review, and `002_seed.sql` holds doctors, slots and sample data.

Rules:
- Plain SQL only. The app accesses these tables through psycopg with parameterised queries (no ORM).
- To re-run the scripts locally, reset the volume with `docker compose down -v`.
- The LangGraph checkpointer creates its own tables at API start-up (`PostgresSaver.setup()`).
