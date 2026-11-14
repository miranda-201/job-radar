-- Where posted_at came from: employer (ATS-published), approximate ("Posted 9 Days Ago"),
-- or list (when a GitHub list added the role; can lag the real posting by days).
ALTER TABLE job_postings ADD COLUMN posted_date_source VARCHAR(16);
-- undergrad | graduate (Master's/PhD/MBA only) | NULL when the source doesn't say.
ALTER TABLE job_postings ADD COLUMN degree_level VARCHAR(16);
CREATE INDEX ix_job_postings_degree_level ON job_postings (degree_level);
