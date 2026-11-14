package com.jobradar.tracker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import com.jobradar.tracker.config.RabbitConfig;
import com.jobradar.tracker.job.JobPostingRepository;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.RabbitMQContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * End-to-end messaging test against real PostgreSQL and RabbitMQ (via Testcontainers).
 * Publishes raw JSON exactly as the Python scraper does (no Java type headers) and checks
 * the consumer persists it, dedupes redeliveries, and dead-letters poison messages.
 * Skipped automatically when Docker is unavailable; always runs in CI.
 */
@SpringBootTest(properties = "jobradar.jwt.secret=test-secret-test-secret-test-secret-test-secret")
@Testcontainers(disabledWithoutDocker = true)
class MessagingPipelineContainerTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Container
    @ServiceConnection
    static RabbitMQContainer rabbit = new RabbitMQContainer("rabbitmq:3.13-management-alpine");

    @Autowired RabbitTemplate rabbitTemplate;
    @Autowired JobPostingRepository jobs;
    @Autowired com.jobradar.tracker.job.JobIngestService ingest;

    private static Message json(String body) {
        return MessageBuilder.withBody(body.getBytes(StandardCharsets.UTF_8))
                .setContentType(MessageProperties.CONTENT_TYPE_JSON)
                .build();
    }

    @Test
    void scraperEventsArePersistedOnceAndPoisonMessagesAreDeadLettered() {
        String event = """
                {"eventId":"e-1","eventType":"job.discovered","source":"workday","company":"NVIDIA",
                 "externalId":"JR2027176","title":"Software Intern - 2027","location":"US, CA, Santa Clara",
                 "url":"https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/x_JR2027176",
                 "postedAt":"2026-11-14T00:00:00Z","discoveredAt":"2026-11-14T15:30:00.123456+00:00",
                 "someFutureField":true}
                """;
        rabbitTemplate.send(RabbitConfig.JOBS_EXCHANGE, RabbitConfig.JOB_DISCOVERED_KEY, json(event));
        rabbitTemplate.send(RabbitConfig.JOBS_EXCHANGE, RabbitConfig.JOB_DISCOVERED_KEY, json(event));

        await().atMost(Duration.ofSeconds(15)).untilAsserted(() ->
                assertThat(jobs.existsBySourceAndCompanyAndExternalId("workday", "NVIDIA", "JR2027176")).isTrue());

        // Missing required fields -> validation fails -> retries exhausted -> DLQ.
        rabbitTemplate.send(RabbitConfig.JOBS_EXCHANGE, RabbitConfig.JOB_DISCOVERED_KEY,
                json("{\"eventId\":\"bad\",\"title\":\"no company\"}"));

        await().atMost(Duration.ofSeconds(20)).untilAsserted(() -> {
            Message dead = rabbitTemplate.receive(RabbitConfig.DEAD_LETTER_QUEUE);
            assertThat(dead).isNotNull();
            assertThat(new String(dead.getBody(), StandardCharsets.UTF_8)).contains("no company");
        });
        assertThat(jobs.existsBySourceAndCompanyAndExternalId("workday", "NVIDIA", "JR2027176")).isTrue();
        assertThat(jobs.findAll()).filteredOn(j -> j.getCompany().equals("NVIDIA")).hasSize(1);
    }

    /** Runs the feed queries on real PostgreSQL (null-parameter handling differs from H2). */
    @Test
    void feedQueriesWorkOnPostgres() {
        var now = java.time.OffsetDateTime.now();
        ingest.ingest(new com.jobradar.tracker.job.JobDiscoveredEvent("e-pg1", "job.discovered", "github_list",
                "PgCo", "pg-1", "Platform Engineer Intern", "Remote", "https://pg.example/1",
                now.minusDays(1), now, "cloud_infra", "Summer 2027"));
        ingest.ingest(new com.jobradar.tracker.job.JobDiscoveredEvent("e-pg2", "job.discovered", "github_list",
                "PgCo", "pg-2", "Data Intern", "Remote", "https://pg.example/2",
                null, now, "data_ml", null));
        var page = org.springframework.data.domain.PageRequest.of(0, 10);
        var epoch = java.time.Instant.EPOCH;

        assertThat(jobs.searchByPostedDate(null, null, null, epoch, page).getTotalElements()).isGreaterThanOrEqualTo(2);
        assertThat(jobs.searchByPostedDate("PgCo", "cloud_infra", "%platform%", epoch, page).getContent())
                .extracting(com.jobradar.tracker.job.JobPosting::getExternalId).containsExactly("pg-1");
        // Undated posting falls back to its discovery time, so it counts as "recent" and sorts first.
        assertThat(jobs.searchByPostedDate("PgCo", null, null, java.time.Instant.now().minusSeconds(3600), page)
                .getContent()).extracting(com.jobradar.tracker.job.JobPosting::getExternalId).containsExactly("pg-2");
        assertThat(jobs.searchByDiscoveredDate("PgCo", null, null, epoch, page).getTotalElements()).isEqualTo(2);
        assertThat(jobs.countByCategory()).isNotEmpty();
    }
}
