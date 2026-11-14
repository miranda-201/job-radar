package com.jobradar.tracker.job;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "job_postings")
public class JobPosting {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 32)
    private String source;

    @Column(nullable = false)
    private String company;

    @Column(name = "external_id", nullable = false)
    private String externalId;

    @Column(nullable = false, length = 500)
    private String title;

    @Column(length = 500)
    private String location;

    @Column(nullable = false, length = 2048)
    private String url;

    @Column(name = "posted_at")
    private Instant postedAt;

    @Column(name = "discovered_at", nullable = false)
    private Instant discoveredAt;

    protected JobPosting() {}

    public JobPosting(String source, String company, String externalId, String title, String location,
                      String url, Instant postedAt, Instant discoveredAt) {
        this.source = source;
        this.company = company;
        this.externalId = externalId;
        this.title = title;
        this.location = location;
        this.url = url;
        this.postedAt = postedAt;
        this.discoveredAt = discoveredAt;
    }

    public Long getId() { return id; }
    public String getSource() { return source; }
    public String getCompany() { return company; }
    public String getExternalId() { return externalId; }
    public String getTitle() { return title; }
    public String getLocation() { return location; }
    public String getUrl() { return url; }
    public Instant getPostedAt() { return postedAt; }
    public Instant getDiscoveredAt() { return discoveredAt; }
}
