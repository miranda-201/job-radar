package com.jobradar.tracker.job;

import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface JobPostingRepository extends JpaRepository<JobPosting, Long> {

    boolean existsBySourceAndCompanyAndExternalId(String source, String company, String externalId);

    @Query("""
            SELECT j FROM JobPosting j
            WHERE (:company IS NULL OR j.company = :company)
              AND (:q IS NULL OR LOWER(j.title) LIKE LOWER(CONCAT('%', CAST(:q AS string), '%'))
                              OR LOWER(j.location) LIKE LOWER(CONCAT('%', CAST(:q AS string), '%')))
            """)
    Page<JobPosting> search(@Param("company") String company, @Param("q") String q, Pageable pageable);

    @Query("SELECT new com.jobradar.tracker.job.CompanyCount(j.company, COUNT(j)) "
            + "FROM JobPosting j GROUP BY j.company ORDER BY j.company")
    List<CompanyCount> countByCompany();
}
