package com.jobradar.tracker.application;

import com.jobradar.tracker.application.ApplicationDtos.ApplicationResponse;
import com.jobradar.tracker.application.ApplicationDtos.CreateApplicationRequest;
import com.jobradar.tracker.application.ApplicationDtos.MoveRequest;
import com.jobradar.tracker.application.ApplicationDtos.StatsResponse;
import com.jobradar.tracker.application.ApplicationDtos.UpdateApplicationRequest;
import com.jobradar.tracker.common.CurrentUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/applications")
@SecurityRequirement(name = "bearer")
public class ApplicationController {

    private final ApplicationService service;

    public ApplicationController(ApplicationService service) {
        this.service = service;
    }

    @GetMapping
    @Operation(summary = "All cards on the current user's board")
    public List<ApplicationResponse> board(@AuthenticationPrincipal Jwt jwt) {
        return service.board(CurrentUser.id(jwt));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Track a scraped job (jobId) or add a manual application")
    public ApplicationResponse create(@AuthenticationPrincipal Jwt jwt, @Valid @RequestBody CreateApplicationRequest req) {
        return service.create(CurrentUser.id(jwt), req);
    }

    @PatchMapping("/{id}")
    @Operation(summary = "Edit card details or notes")
    public ApplicationResponse update(@AuthenticationPrincipal Jwt jwt, @PathVariable Long id,
                                      @Valid @RequestBody UpdateApplicationRequest req) {
        return service.update(CurrentUser.id(jwt), id, req);
    }

    @PutMapping("/{id}/move")
    @Operation(summary = "Drag-and-drop: move a card to a column and position")
    public ApplicationResponse move(@AuthenticationPrincipal Jwt jwt, @PathVariable Long id,
                                    @Valid @RequestBody MoveRequest req) {
        return service.move(CurrentUser.id(jwt), id, req);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@AuthenticationPrincipal Jwt jwt, @PathVariable Long id) {
        service.delete(CurrentUser.id(jwt), id);
    }

    @GetMapping("/stats")
    @Operation(summary = "Funnel counts per status")
    public StatsResponse stats(@AuthenticationPrincipal Jwt jwt) {
        return service.stats(CurrentUser.id(jwt));
    }
}
