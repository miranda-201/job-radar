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

    @Column(length = 32)
    private String category;

    @Column(length = 64)
    private String term;

    @Column(name = "canonical_url", length = 2048)
    private String canonicalUrl;

    @Column(length = 800)
    private String fingerprint;

    @Column(name = "posted_date_source", length = 16)
    private String postedDateSource;

    @Column(name = "degree_level", length = 16)
    private String degreeLevel;

    protected JobPosting() {}

    public JobPosting(String source, String company, String externalId, String title, String location,
                      String url, Instant postedAt, Instant discoveredAt, String category, String term,
                      String postedDateSource, String degreeLevel) {
        this.source = source;
        this.company = company;
        this.externalId = externalId;
        this.title = title;
        this.location = location;
        this.url = url;
        this.postedAt = postedAt;
        this.discoveredAt = discoveredAt;
        this.category = category;
        this.term = term;
        this.canonicalUrl = Dedup.canonicalUrl(url);
        this.fingerprint = Dedup.fingerprint(company, title);
        this.postedDateSource = postedDateSource;
        this.degreeLevel = degreeLevel;
    }

    /**
     * Merge another sighting of the same role: an employer-verified date replaces a
     * list/approximate one; category and degree level (derived by the scraper's classifier)
     * take the newest non-null value so classifier fixes reach existing rows; a missing term
     * is filled in. Returns true if anything changed.
     */
    public boolean improveFrom(Instant otherPostedAt, String otherDateSource, String otherCategory,
                               String otherTerm, String otherDegreeLevel) {
        boolean changed = false;
        if ("employer".equals(otherDateSource) && otherPostedAt != null && !"employer".equals(postedDateSource)) {
            postedAt = otherPostedAt;
            postedDateSource = "employer";
            changed = true;
        }
        if (otherCategory != null && !otherCategory.equals(category)) { category = otherCategory; changed = true; }
        if (term == null && otherTerm != null) { term = otherTerm; changed = true; }
        if (otherDegreeLevel != null && !otherDegreeLevel.equals(degreeLevel)) {
            degreeLevel = otherDegreeLevel;
            changed = true;
        }
        return changed;
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
    public String getCategory() { return category; }
    public String getTerm() { return term; }
    public String getCanonicalUrl() { return canonicalUrl; }
    public String getFingerprint() { return fingerprint; }
    public String getPostedDateSource() { return postedDateSource; }
    public String getDegreeLevel() { return degreeLevel; }
}
