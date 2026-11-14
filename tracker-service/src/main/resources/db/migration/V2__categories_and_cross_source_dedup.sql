-- Role category (software / data_ml / cloud_infra / security) and season ("Summer 2027").
ALTER TABLE job_postings ADD COLUMN category VARCHAR(32);
ALTER TABLE job_postings ADD COLUMN term VARCHAR(64);

-- Cross-source dedup: the same role is often listed on its company's ATS *and* on GitHub
-- lists. canonical_url is the URL without tracking params; fingerprint is
-- normalized "company|title". Neither is unique: a role can legitimately be re-posted later.
ALTER TABLE job_postings ADD COLUMN canonical_url VARCHAR(2048);
ALTER TABLE job_postings ADD COLUMN fingerprint VARCHAR(800);
UPDATE job_postings SET canonical_url = url;

CREATE INDEX ix_job_postings_canonical_url ON job_postings (canonical_url);
CREATE INDEX ix_job_postings_fingerprint ON job_postings (fingerprint);
CREATE INDEX ix_job_postings_category ON job_postings (category);
CREATE INDEX ix_job_postings_posted_at ON job_postings (posted_at DESC);
