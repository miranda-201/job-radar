package com.jobradar.tracker.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.rabbit.annotation.RabbitListenerConfigurer;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Topology owned by this consumer. The scraper only knows the topic exchange, so each
 * consumer service declares (and scales) its own queue independently.
 */
@Configuration
public class RabbitConfig {

    public static final String JOBS_EXCHANGE = "jobs.events";
    public static final String JOB_DISCOVERED_KEY = "job.discovered";
    public static final String JOB_DISCOVERED_QUEUE = "tracker.job-discovered";
    public static final String DEAD_LETTER_EXCHANGE = "jobs.dlx";
    public static final String DEAD_LETTER_QUEUE = "tracker.job-discovered.dlq";

    @Bean
    TopicExchange jobsExchange() {
        return new TopicExchange(JOBS_EXCHANGE, true, false);
    }

    @Bean
    DirectExchange deadLetterExchange() {
        return new DirectExchange(DEAD_LETTER_EXCHANGE, true, false);
    }

    @Bean
    Queue jobDiscoveredQueue() {
        return QueueBuilder.durable(JOB_DISCOVERED_QUEUE)
                .deadLetterExchange(DEAD_LETTER_EXCHANGE)
                .deadLetterRoutingKey(DEAD_LETTER_QUEUE)
                .build();
    }

    @Bean
    Queue deadLetterQueue() {
        return QueueBuilder.durable(DEAD_LETTER_QUEUE).build();
    }

    @Bean
    Binding jobDiscoveredBinding() {
        return BindingBuilder.bind(jobDiscoveredQueue()).to(jobsExchange()).with(JOB_DISCOVERED_KEY);
    }

    @Bean
    Binding deadLetterBinding() {
        return BindingBuilder.bind(deadLetterQueue()).to(deadLetterExchange()).with(DEAD_LETTER_QUEUE);
    }

    /** Enables @Valid on @RabbitListener payloads; invalid events end up in the DLQ. */
    @Bean
    RabbitListenerConfigurer rabbitListenerValidation(LocalValidatorFactoryBean validator) {
        return registrar -> registrar.setValidator(validator);
    }

    /** JSON in, typed records out (type inferred from the listener method parameter). */
    @Bean
    MessageConverter jsonMessageConverter(ObjectMapper objectMapper) {
        return new Jackson2JsonMessageConverter(objectMapper);
    }
}
