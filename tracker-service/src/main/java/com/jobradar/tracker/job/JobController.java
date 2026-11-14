package com.jobradar.tracker.job;

import com.jobradar.tracker.application.JobApplicationRepository;
import com.jobradar.tracker.common.CurrentUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/jobs")
@SecurityRequirement(name = "bearer")
@Transactional(readOnly = true)
public class JobController {

    private final JobPostingRepository jobs;
    private final JobApplicationRepository applications;

    public JobController(JobPostingRepository jobs, JobApplicationRepository applications) {
        this.jobs = jobs;
        this.applications = applications;
    }

    public record JobResponse(Long id, String source, String company, String title, String location, String url,
                              Instant postedAt, Instant discoveredAt, boolean tracked) {}

    public record PageResponse<T>(List<T> items, int page, int size, long totalItems, int totalPages) {}

    @GetMapping
    @Operation(summary = "Feed of discovered postings, newest first")
    public PageResponse<JobResponse> list(@AuthenticationPrincipal Jwt jwt,
                                          @RequestParam(required = false) String company,
                                          @RequestParam(required = false) String q,
                                          @RequestParam(defaultValue = "0") int page,
                                          @RequestParam(defaultValue = "25") int size) {
        var pageable = PageRequest.of(Math.max(page, 0), Math.clamp(size, 1, 100),
                Sort.by(Sort.Direction.DESC, "discoveredAt").and(Sort.by("id")));
        Page<JobPosting> result = jobs.search(blankToNull(company), blankToNull(q), pageable);

        List<Long> ids = result.getContent().stream().map(JobPosting::getId).toList();
        Set<Long> tracked = ids.isEmpty() ? Set.of() : applications.findTrackedJobIds(CurrentUser.id(jwt), ids);

        List<JobResponse> items = result.getContent().stream()
                .map(j -> new JobResponse(j.getId(), j.getSource(), j.getCompany(), j.getTitle(), j.getLocation(),
                        j.getUrl(), j.getPostedAt(), j.getDiscoveredAt(), tracked.contains(j.getId())))
                .toList();
        return new PageResponse<>(items, result.getNumber(), result.getSize(), result.getTotalElements(),
                result.getTotalPages());
    }

    @GetMapping("/companies")
    @Operation(summary = "Companies with at least one discovered posting")
    public List<CompanyCount> companies() {
        return jobs.countByCompany();
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
