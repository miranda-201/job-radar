package com.jobradar.tracker.application;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.Map;

public final class ApplicationDtos {

    private ApplicationDtos() {}

    /** Either {@code jobId} (track a scraped posting) or company + roleTitle (manual entry). */
    public record CreateApplicationRequest(
            Long jobId,
            @Size(max = 255) String company,
            @Size(max = 500) String roleTitle,
            @Size(max = 2048) String url,
            @Size(max = 500) String location,
            ApplicationStatus status,
            @Size(max = 4000) String notes) {}

    public record UpdateApplicationRequest(
            @Size(max = 255) String company,
            @Size(max = 500) String roleTitle,
            @Size(max = 2048) String url,
            @Size(max = 500) String location,
            @Size(max = 4000) String notes) {}

    /** Drag-and-drop: move a card to {@code status} at index {@code position} in that column. */
    public record MoveRequest(@NotNull ApplicationStatus status, @NotNull @Min(0) Integer position) {}

    public record ApplicationResponse(
            Long id,
            Long jobId,
            String company,
            String roleTitle,
            String url,
            String location,
            ApplicationStatus status,
            int position,
            String notes,
            Instant appliedAt,
            Instant createdAt,
            Instant updatedAt) {

        static ApplicationResponse from(JobApplication a) {
            return new ApplicationResponse(
                    a.getId(), a.getJob() != null ? a.getJob().getId() : null, a.getCompany(), a.getRoleTitle(),
                    a.getUrl(), a.getLocation(), a.getStatus(), a.getPosition(), a.getNotes(),
                    a.getAppliedAt(), a.getCreatedAt(), a.getUpdatedAt());
        }
    }

    public record StatsResponse(long total, long applied, Map<ApplicationStatus, Long> byStatus) {}
}
