package com.jobradar.tracker.job;

import java.time.Instant;
import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface JobPostingRepository extends JpaRepository<JobPosting, Long> {

    boolean existsBySourceAndCompanyAndExternalId(String source, String company, String externalId);

    boolean existsByCanonicalUrl(String canonicalUrl);

    boolean existsByFingerprintAndDiscoveredAtAfter(String fingerprint, Instant after);

    /**
     * Shared filter. {@code q} must already be a lower-cased LIKE pattern ("%term%").
     * A posting with no known publish date is treated as posted when it was discovered,
     * which is an upper bound and keeps it in date filters and sorting.
     */
    String FILTER = """
            FROM JobPosting j
            WHERE (:company IS NULL OR j.company = :company)
              AND (:category IS NULL OR j.category = :category)
              AND COALESCE(j.postedAt, j.discoveredAt) >= :since
              AND (:q IS NULL OR LOWER(j.title) LIKE :q OR LOWER(j.company) LIKE :q OR LOWER(j.location) LIKE :q)
            """;

    @Query(value = "SELECT j " + FILTER + " ORDER BY COALESCE(j.postedAt, j.discoveredAt) DESC, j.id DESC",
            countQuery = "SELECT COUNT(j) " + FILTER)
    Page<JobPosting> searchByPostedDate(@Param("company") String company, @Param("category") String category,
                                        @Param("q") String q, @Param("since") Instant since, Pageable pageable);

    @Query(value = "SELECT j " + FILTER + " ORDER BY j.discoveredAt DESC, j.id DESC",
            countQuery = "SELECT COUNT(j) " + FILTER)
    Page<JobPosting> searchByDiscoveredDate(@Param("company") String company, @Param("category") String category,
                                            @Param("q") String q, @Param("since") Instant since, Pageable pageable);

    @Query("SELECT new com.jobradar.tracker.job.CompanyCount(j.company, COUNT(j)) "
            + "FROM JobPosting j GROUP BY j.company ORDER BY j.company")
    List<CompanyCount> countByCompany();

    @Query("SELECT new com.jobradar.tracker.job.CategoryCount(j.category, COUNT(j)) "
            + "FROM JobPosting j WHERE j.category IS NOT NULL GROUP BY j.category ORDER BY COUNT(j) DESC")
    List<CategoryCount> countByCategory();
}
