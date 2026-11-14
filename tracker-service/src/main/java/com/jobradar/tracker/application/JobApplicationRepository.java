package com.jobradar.tracker.application;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface JobApplicationRepository extends JpaRepository<JobApplication, Long> {

    List<JobApplication> findByUserIdOrderByStatusAscPositionAsc(Long userId);

    List<JobApplication> findByUserIdAndStatusOrderByPositionAsc(Long userId, ApplicationStatus status);

    Optional<JobApplication> findByIdAndUserId(Long id, Long userId);

    boolean existsByUserIdAndJobId(Long userId, Long jobId);

    int countByUserIdAndStatus(Long userId, ApplicationStatus status);

    @Query("SELECT a.job.id FROM JobApplication a WHERE a.user.id = :userId AND a.job.id IN :jobIds")
    Set<Long> findTrackedJobIds(@Param("userId") Long userId, @Param("jobIds") Collection<Long> jobIds);

    @Query("SELECT a.status AS status, COUNT(a) AS total FROM JobApplication a "
            + "WHERE a.user.id = :userId GROUP BY a.status")
    List<StatusCount> countByStatus(@Param("userId") Long userId);

    interface StatusCount {
        ApplicationStatus getStatus();
        long getTotal();
    }
}
