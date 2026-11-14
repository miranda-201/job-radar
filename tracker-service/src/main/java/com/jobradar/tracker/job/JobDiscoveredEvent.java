package com.jobradar.tracker.job;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.constraints.NotBlank;
import java.time.OffsetDateTime;

/**
 * Message contract published by scraper-service on exchange {@code jobs.events},
 * routing key {@code job.discovered}. Unknown fields are ignored so the producer can
 * add fields without breaking this consumer.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record JobDiscoveredEvent(
        String eventId,
        String eventType,
        @NotBlank String source,
        @NotBlank String company,
        @NotBlank String externalId,
        @NotBlank String title,
        String location,
        @NotBlank String url,
        OffsetDateTime postedAt,
        OffsetDateTime discoveredAt) {}
