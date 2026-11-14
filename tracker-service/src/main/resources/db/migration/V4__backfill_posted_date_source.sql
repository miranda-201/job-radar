-- Rows ingested before V3 have no date source. Before date verification existed, GitHub-list
-- dates were always "added to list" dates and Workday dates were "Posted N days ago"
-- estimates, so label them honestly rather than presenting them as employer-published.
UPDATE job_postings
SET posted_date_source = CASE source
        WHEN 'github_list' THEN 'list'
        WHEN 'workday' THEN 'approximate'
        ELSE 'employer'
    END
WHERE posted_date_source IS NULL;
