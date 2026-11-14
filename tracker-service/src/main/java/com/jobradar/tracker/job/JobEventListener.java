package com.jobradar.tracker.job;

import com.jobradar.tracker.config.RabbitConfig;
import jakarta.validation.Valid;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Component
public class JobEventListener {

    private final JobIngestService ingestService;

    public JobEventListener(JobIngestService ingestService) {
        this.ingestService = ingestService;
    }

    /**
     * Failures are retried in-process (see spring.rabbitmq.listener.simple.retry) and then
     * rejected without requeue, which routes the message to the dead-letter queue.
     */
    @RabbitListener(queues = RabbitConfig.JOB_DISCOVERED_QUEUE)
    public void onJobDiscovered(@Valid JobDiscoveredEvent event) {
        ingestService.ingest(event);
    }
}
