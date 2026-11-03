-- Doctors
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL
);

-- Appointment slots
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT valid_slot_time CHECK (ends_at > starts_at),
    -- prevent duplicate slots at the database level
     CONSTRAINT unique_doctor_slot
        UNIQUE (doctor_id, starts_at, ends_at)
);


-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bookings
-- reject to avoid duplications in bookings
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slot_id INTEGER NOT NULL REFERENCES slots(id),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_approval',

    CONSTRAINT valid_booking_status
        CHECK (status IN (
            'pending_approval',
            'confirmed',
            'cancelled',
            'rejected'
        ))
);
-- Why do we add it after creating the table? Because an index operates on an existing table.
CREATE UNIQUE INDEX IF NOT EXISTS unique_active_booking_per_slot
ON bookings (slot_id)
WHERE status IN ('pending_approval', 'confirmed');

-- Approvals
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    booking_id INTEGER NOT NULL REFERENCES bookings(id),
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,

    CONSTRAINT valid_approval_action
        CHECK (action IN ('book', 'cancel')),

    CONSTRAINT valid_approval_status
        CHECK (status IN ('pending', 'approved', 'rejected')),

    CONSTRAINT valid_approval_decision
        CHECK (
            (status = 'pending' AND decided_at IS NULL)
            OR
            (status IN ('approved', 'rejected') AND decided_at IS NOT NULL)
        )
);

-- Emergency flags
CREATE TABLE IF NOT EXISTS emergency_flags (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Document chunks for RAG
CREATE TABLE IF NOT EXISTS doc_chunks (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,

    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', content)
    ) STORED,

    CONSTRAINT unique_document_chunk
        UNIQUE (source, chunk_index)
);

-- Speed up full-text searches
-- If the index doesn't exist, create it.
-- If it already exists, skip creating it.
CREATE INDEX IF NOT EXISTS idx_doc_chunks_search
ON doc_chunks USING GIN (search_vector);