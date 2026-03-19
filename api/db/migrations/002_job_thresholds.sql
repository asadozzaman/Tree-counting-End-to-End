-- 002_job_thresholds.sql
ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS conf_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.25,
ADD COLUMN IF NOT EXISTS iou_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.45;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'jobs_conf_threshold_range'
    ) THEN
        ALTER TABLE jobs
        ADD CONSTRAINT jobs_conf_threshold_range CHECK (conf_threshold >= 0 AND conf_threshold <= 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'jobs_iou_threshold_range'
    ) THEN
        ALTER TABLE jobs
        ADD CONSTRAINT jobs_iou_threshold_range CHECK (iou_threshold >= 0 AND iou_threshold <= 1);
    END IF;
END $$;
