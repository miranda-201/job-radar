package com.jobradar.tracker.job;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

/**
 * Idempotent ingestion of job events: safe under redelivery and duplicate publishes, and
 * collapses the same role arriving from different sources (company ATS + GitHub lists).
 */
@Service
public class JobIngestService {

    private static final Logger log = LoggerFactory.getLogger(JobIngestService.class);

    /** Same company + title within this window is treated as one role, not a re-post. */
    static final Duration CROSS_SOURCE_WINDOW = Duration.ofDays(60);

    private final JobPostingRepository jobs;
    private final Counter ingested;
    private final Counter duplicates;
    private final Counter crossSourceDuplicates;

    public JobIngestService(JobPostingRepository jobs, MeterRegistry meters) {
        this.jobs = jobs;
        this.ingested = meters.counter("tracker.jobs.ingested");
        this.duplicates = meters.counter("tracker.jobs.duplicates");
        this.crossSourceDuplicates = meters.counter("tracker.jobs.cross_source_duplicates");
    }

    public enum Outcome { CREATED, DUPLICATE, CROSS_SOURCE_DUPLICATE }

    public Outcome ingest(JobDiscoveredEvent e) {
        if (jobs.existsBySourceAndCompanyAndExternalId(e.source(), e.company(), e.externalId())) {
            duplicates.increment();
            return Outcome.DUPLICATE;
        }
        String title = truncate(e.title(), 500);
        Instant now = Instant.now();
        if (jobs.existsByCanonicalUrl(Dedup.canonicalUrl(e.url()))
                || jobs.existsByFingerprintAndDiscoveredAtAfter(
                        Dedup.fingerprint(e.company(), title), now.minus(CROSS_SOURCE_WINDOW))) {
            crossSourceDuplicates.increment();
            return Outcome.CROSS_SOURCE_DUPLICATE;
        }
        try {
            jobs.saveAndFlush(new JobPosting(
                    e.source(), e.company(), e.externalId(), title, truncate(e.location(), 500), e.url(),
                    toInstant(e.postedAt()), e.discoveredAt() != null ? e.discoveredAt().toInstant() : now,
                    truncate(e.category(), 32), truncate(e.term(), 64)));
        } catch (DataIntegrityViolationException race) {
            // Another consumer inserted the same posting between our check and insert.
            duplicates.increment();
            return Outcome.DUPLICATE;
        }
        ingested.increment();
        log.debug("ingested {} posting '{}' at {}", e.source(), e.title(), e.company());
        return Outcome.CREATED;
    }

    private static Instant toInstant(OffsetDateTime t) {
        return t == null ? null : t.toInstant();
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }
}
