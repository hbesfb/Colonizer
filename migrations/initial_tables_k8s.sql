-- Quoting table and column names to enforce case sensitivity (required for PostgreSQL)
-- if not quoted, PostgreSQL will convert them to lowercase yet Colonizer expects them to be as defined here
CREATE TABLE IF NOT EXISTS "SETTLEPLATE" (
    "ID" SERIAL PRIMARY KEY,
    "Username" VARCHAR(32),
    "ScanDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Barcode" VARCHAR(128),
    -- Adding column such that in future if we decide to save data to it,it already exists.
    -- For now entries in DB will have NULL for PlateSerial because the model.py and register.py dont add data to it
    "PlateSerial" VARCHAR(128),
    "Lot_no" VARCHAR(64),
    "Expires" DATE,
    "Counts" INTEGER,
    "Version" VARCHAR(32),
    "Location" VARCHAR(128),
    "Batch" VARCHAR(128),
    "Image" BYTEA,
    "Colonies" TEXT,
    "Exported" BOOLEAN DEFAULT FALSE,
     CONSTRAINT unique_batch_location UNIQUE ("Batch", "Location")
);

-- unique_registration_barcode prevents the same barcode being registered twice as a pending plate, 
-- But it also means the same barcode can appear unlimited times once 
-- Counts is updated away from -1.
CREATE UNIQUE INDEX IF NOT EXISTS unique_registration_barcode
    ON "SETTLEPLATE" ("Barcode")
    WHERE "Counts" = -1;

-- directly serves batch_bydate query and positive test lookup
-- positive check in tools.py filters on batch, batch_dybate also filters on batch
CREATE INDEX IF NOT EXISTS idx_batch
    ON "SETTLEPLATE" ("Batch");