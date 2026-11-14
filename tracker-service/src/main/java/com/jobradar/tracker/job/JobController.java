package com.jobradar.tracker.job;

import com.jobradar.tracker.application.JobApplicationRepository;
import com.jobradar.tracker.common.CurrentUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/jobs")
@SecurityRequirement(name = "bearer")
@Transactional(readOnly = true)
public class JobController {

    private static final Set<String> CATEGORIES = Set.of("software", "data_ml", "cloud_infra", "security");

    private final JobPostingRepository jobs;
    private final JobApplicationRepository applications;

    public JobController(JobPostingRepository jobs, JobApplicationRepository applications) {
        this.jobs = jobs;
        this.applications = applications;
    }

    public record JobResponse(Long id, String source, String company, String title, String location, String url,
                              Instant postedAt, String postedDateSource, Instant discoveredAt, String category,
                              String term, String degreeLevel, boolean tracked) {}

    public record PageResponse<T>(List<T> items, int page, int size, long totalItems, int totalPages) {}

    @GetMapping
    @Operation(summary = "Feed of discovered postings")
    public PageResponse<JobResponse> list(
            @AuthenticationPrincipal Jwt jwt,
            @RequestParam(required = false) String company,
            @RequestParam(required = false) @Parameter(description = "Search title, company and location") String q,
            @RequestParam(required = false) @Parameter(description = "software | data_ml | cloud_infra | security")
            String category,
            @RequestParam(required = false) @Parameter(description = "Only postings published in the last N days")
            Integer postedWithinDays,
            @RequestParam(defaultValue = "posted") @Parameter(description = "posted (newest posting date first) | discovered")
            String sort,
            @RequestParam(defaultValue = "false") @Parameter(description = "Hide Master's/PhD-only postings")
            boolean undergradOnly,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "25") int size) {

        String cat = blankToNull(category);
        if (cat != null && !CATEGORIES.contains(cat)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown category: " + cat);
        }
        if (!sort.equals("posted") && !sort.equals("discovered")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sort must be 'posted' or 'discovered'");
        }
        Instant since = postedWithinDays == null || postedWithinDays <= 0
                ? Instant.EPOCH
                : Instant.now().minus(Duration.ofDays(postedWithinDays));
        String pattern = blankToNull(q) == null ? null : "%" + q.trim().toLowerCase(Locale.ROOT) + "%";
        var pageable = PageRequest.of(Math.max(page, 0), Math.clamp(size, 1, 100));

        Page<JobPosting> result = sort.equals("posted")
                ? jobs.searchByPostedDate(blankToNull(company), cat, pattern, since, undergradOnly, pageable)
                : jobs.searchByDiscoveredDate(blankToNull(company), cat, pattern, since, undergradOnly, pageable);

        List<Long> ids = result.getContent().stream().map(JobPosting::getId).toList();
        Set<Long> tracked = ids.isEmpty() ? Set.of() : applications.findTrackedJobIds(CurrentUser.id(jwt), ids);

        List<JobResponse> items = result.getContent().stream()
                .map(j -> new JobResponse(j.getId(), j.getSource(), j.getCompany(), j.getTitle(), j.getLocation(),
                        j.getUrl(), j.getPostedAt(), j.getPostedDateSource(), j.getDiscoveredAt(), j.getCategory(),
                        j.getTerm(), j.getDegreeLevel(), tracked.contains(j.getId())))
                .toList();
        return new PageResponse<>(items, result.getNumber(), result.getSize(), result.getTotalElements(),
                result.getTotalPages());
    }

    @GetMapping("/companies")
    @Operation(summary = "Companies with at least one discovered posting")
    public List<CompanyCount> companies() {
        return jobs.countByCompany();
    }

    @GetMapping("/categories")
    @Operation(summary = "Posting counts per role category")
    public List<CategoryCount> categories() {
        return jobs.countByCategory();
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
