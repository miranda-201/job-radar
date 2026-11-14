package com.jobradar.tracker.application;

import com.jobradar.tracker.application.ApplicationDtos.ApplicationResponse;
import com.jobradar.tracker.application.ApplicationDtos.CreateApplicationRequest;
import com.jobradar.tracker.application.ApplicationDtos.MoveRequest;
import com.jobradar.tracker.application.ApplicationDtos.StatsResponse;
import com.jobradar.tracker.application.ApplicationDtos.UpdateApplicationRequest;
import com.jobradar.tracker.job.JobPosting;
import com.jobradar.tracker.job.JobPostingRepository;
import com.jobradar.tracker.user.AppUser;
import com.jobradar.tracker.user.UserRepository;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
@Transactional
public class ApplicationService {

    private final JobApplicationRepository applications;
    private final JobPostingRepository jobs;
    private final UserRepository users;

    public ApplicationService(JobApplicationRepository applications, JobPostingRepository jobs, UserRepository users) {
        this.applications = applications;
        this.jobs = jobs;
        this.users = users;
    }

    @Transactional(readOnly = true)
    public List<ApplicationResponse> board(Long userId) {
        return applications.findByUserIdOrderByStatusAscPositionAsc(userId).stream()
                .map(ApplicationResponse::from)
                .toList();
    }

    public ApplicationResponse create(Long userId, CreateApplicationRequest req) {
        AppUser user = users.getReferenceById(userId);
        ApplicationStatus status = req.status() != null ? req.status() : ApplicationStatus.SAVED;
        int position = applications.countByUserIdAndStatus(userId, status);

        JobApplication app;
        if (req.jobId() != null) {
            JobPosting job = jobs.findById(req.jobId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "job not found"));
            if (applications.existsByUserIdAndJobId(userId, job.getId())) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "this job is already on your board");
            }
            app = new JobApplication(user, job, job.getCompany(), job.getTitle(), job.getUrl(), job.getLocation(),
                    status, position, req.notes());
        } else {
            if (isBlank(req.company()) || isBlank(req.roleTitle())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "company and roleTitle are required when jobId is not provided");
            }
            app = new JobApplication(user, null, req.company().trim(), req.roleTitle().trim(), req.url(),
                    req.location(), status, position, req.notes());
        }
        return ApplicationResponse.from(applications.save(app));
    }

    public ApplicationResponse update(Long userId, Long id, UpdateApplicationRequest req) {
        JobApplication app = load(userId, id);
        if (!isBlank(req.company())) app.setCompany(req.company().trim());
        if (!isBlank(req.roleTitle())) app.setRoleTitle(req.roleTitle().trim());
        if (req.url() != null) app.setUrl(req.url());
        if (req.location() != null) app.setLocation(req.location());
        if (req.notes() != null) app.setNotes(req.notes());
        return ApplicationResponse.from(app);
    }

    /**
     * Moves a card to (status, position) and renumbers the affected columns so positions stay
     * dense (0..n-1). Columns are small (tens of cards), so a full renumber is simpler and safer
     * than gap-based ordering.
     */
    public ApplicationResponse move(Long userId, Long id, MoveRequest req) {
        JobApplication app = load(userId, id);
        ApplicationStatus from = app.getStatus();
        ApplicationStatus to = req.status();

        List<JobApplication> target = new ArrayList<>(
                applications.findByUserIdAndStatusOrderByPositionAsc(userId, to));
        target.removeIf(a -> a.getId().equals(app.getId()));
        target.add(Math.min(req.position(), target.size()), app);

        app.changeStatus(to);
        renumber(target);
        if (from != to) {
            renumber(applications.findByUserIdAndStatusOrderByPositionAsc(userId, from).stream()
                    .filter(a -> !a.getId().equals(app.getId()))
                    .toList());
        }
        return ApplicationResponse.from(app);
    }

    public void delete(Long userId, Long id) {
        JobApplication app = load(userId, id);
        applications.delete(app);
        applications.flush();
        renumber(applications.findByUserIdAndStatusOrderByPositionAsc(userId, app.getStatus()));
    }

    @Transactional(readOnly = true)
    public StatsResponse stats(Long userId) {
        Map<ApplicationStatus, Long> byStatus = new EnumMap<>(ApplicationStatus.class);
        for (ApplicationStatus s : ApplicationStatus.values()) byStatus.put(s, 0L);
        applications.countByStatus(userId).forEach(c -> byStatus.put(c.getStatus(), c.getTotal()));
        long total = byStatus.values().stream().mapToLong(Long::longValue).sum();
        long applied = byStatus.entrySet().stream()
                .filter(e -> e.getKey().countsAsApplied())
                .mapToLong(Map.Entry::getValue).sum();
        return new StatsResponse(total, applied, byStatus);
    }

    private JobApplication load(Long userId, Long id) {
        // Scoped by user: another user's card id behaves exactly like a missing one (no IDOR leak).
        return applications.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "application not found"));
    }

    private static void renumber(List<JobApplication> column) {
        for (int i = 0; i < column.size(); i++) column.get(i).setPosition(i);
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }
}
