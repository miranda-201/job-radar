package com.jobradar.tracker.config;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "jobradar.jwt")
public record JwtProperties(
        @NotNull @Size(min = 32, message = "HS256 needs a secret of at least 32 bytes") String secret,
        @NotNull Duration ttl) {}
