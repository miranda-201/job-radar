package com.jobradar.tracker.job;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Instant;
import java.time.OffsetDateTime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

/** Idempotent ingestion of job events: safe under redelivery and duplicate publishes. */
@Service
public class JobIngestService {

    private static final Logger log = LoggerFactory.getLogger(JobIngestService.class);

    private final JobPostingRepository jobs;
    private final Counter ingested;
    private final Counter duplicates;

    public JobIngestService(JobPostingRepository jobs, MeterRegistry meters) {
        this.jobs = jobs;
        this.ingested = meters.counter("tracker.jobs.ingested");
        this.duplicates = meters.counter("tracker.jobs.duplicates");
    }

    public enum Outcome { CREATED, DUPLICATE }

    public Outcome ingest(JobDiscoveredEvent e) {
        if (jobs.existsBySourceAndCompanyAndExternalId(e.source(), e.company(), e.externalId())) {
            duplicates.increment();
            return Outcome.DUPLICATE;
        }
        try {
            jobs.saveAndFlush(new JobPosting(
                    e.source(), e.company(), e.externalId(), truncate(e.title(), 500),
                    truncate(e.location(), 500), e.url(), toInstant(e.postedAt()),
                    e.discoveredAt() != null ? e.discoveredAt().toInstant() : Instant.now()));
        } catch (DataIntegrityViolationException race) {
            // Another consumer inserted the same posting between our check and insert.
            duplicates.increment();
            return Outcome.DUPLICATE;
        }
        ingested.increment();
        log.info("ingested {} posting '{}' at {}", e.source(), e.title(), e.company());
        return Outcome.CREATED;
    }

    private static Instant toInstant(OffsetDateTime t) {
        return t == null ? null : t.toInstant();
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }
}
