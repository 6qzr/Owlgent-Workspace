-- Insert doctors
INSERT INTO doctors (name, specialty)
SELECT seed.name, seed.specialty
FROM (
    VALUES
        ('Dr. Ahmed', 'General Practice'),
        ('Dr. Fatima', 'General Practice'),
        ('Dr. Sara', 'Dentistry'),
        ('Dr. Khalid', 'Dentistry')
) AS seed(name, specialty)
-- prevents inserting the same doctor again if the seed script is executed more than once.
WHERE NOT EXISTS (
    SELECT 1
    FROM doctors
    WHERE doctors.name = seed.name
      AND doctors.specialty = seed.specialty
);

-- Generate appointment slots for the next five days
WITH days AS (
    SELECT
        (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Muscat')::date + day_offset
        AS appointment_date
    FROM generate_series(1, 5) AS day_offset
),

appointment_times AS (
    SELECT slot_time
    FROM (
        VALUES
            (TIME '09:00'),
            (TIME '09:30'),
            (TIME '10:00'),
            (TIME '10:30'),
            (TIME '11:00'),
            (TIME '11:30'),
            (TIME '13:00'),
            (TIME '13:30'),
            (TIME '14:00'),
            (TIME '14:30'),
            (TIME '15:00'),
            (TIME '15:30')
    ) AS times(slot_time)
),

new_slots AS (
    SELECT
        doctors.id AS doctor_id,
        (days.appointment_date + appointment_times.slot_time)
            AT TIME ZONE 'Asia/Muscat' AS starts_at
    FROM doctors
    CROSS JOIN days
    CROSS JOIN appointment_times
)

INSERT INTO slots (doctor_id, starts_at, ends_at)
SELECT
    new_slots.doctor_id,
    new_slots.starts_at,
    new_slots.starts_at + INTERVAL '30 minutes'
FROM new_slots
WHERE NOT EXISTS (
    SELECT 1
    FROM slots
    WHERE slots.doctor_id = new_slots.doctor_id
      AND slots.starts_at = new_slots.starts_at
      AND slots.ends_at = new_slots.starts_at + INTERVAL '30 minutes'
);