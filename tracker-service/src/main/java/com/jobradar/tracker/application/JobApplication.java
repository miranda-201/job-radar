package com.jobradar.tracker.application;

import com.jobradar.tracker.job.JobPosting;
import com.jobradar.tracker.user.AppUser;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;

/** One card on a user's Kanban board. */
@Entity
@Table(name = "job_applications")
public class JobApplication {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private AppUser user;

    /** Null for applications the user entered by hand (not found by the scraper). */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "job_id")
    private JobPosting job;

    @Column(nullable = false)
    private String company;

    @Column(name = "role_title", nullable = false, length = 500)
    private String roleTitle;

    @Column(length = 2048)
    private String url;

    @Column(length = 500)
    private String location;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ApplicationStatus status;

    @Column(nullable = false)
    private int position;

    @Column(length = 4000)
    private String notes;

    @Column(name = "applied_at")
    private Instant appliedAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected JobApplication() {}

    public JobApplication(AppUser user, JobPosting job, String company, String roleTitle, String url,
                          String location, ApplicationStatus status, int position, String notes) {
        this.user = user;
        this.job = job;
        this.company = company;
        this.roleTitle = roleTitle;
        this.url = url;
        this.location = location;
        this.position = position;
        this.notes = notes;
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
        changeStatus(status);
    }

    public void changeStatus(ApplicationStatus newStatus) {
        this.status = newStatus;
        if (newStatus.countsAsApplied() && appliedAt == null) {
            appliedAt = Instant.now();
        }
    }

    @PreUpdate
    void touch() {
        updatedAt = Instant.now();
    }

    public Long getId() { return id; }
    public AppUser getUser() { return user; }
    public JobPosting getJob() { return job; }
    public String getCompany() { return company; }
    public String getRoleTitle() { return roleTitle; }
    public String getUrl() { return url; }
    public String getLocation() { return location; }
    public ApplicationStatus getStatus() { return status; }
    public int getPosition() { return position; }
    public String getNotes() { return notes; }
    public Instant getAppliedAt() { return appliedAt; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public void setPosition(int position) { this.position = position; }
    public void setNotes(String notes) { this.notes = notes; }
    public void setCompany(String company) { this.company = company; }
    public void setRoleTitle(String roleTitle) { this.roleTitle = roleTitle; }
    public void setUrl(String url) { this.url = url; }
    public void setLocation(String location) { this.location = location; }
}
