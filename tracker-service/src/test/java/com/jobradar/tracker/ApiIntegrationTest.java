package com.jobradar.tracker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jobradar.tracker.job.JobDiscoveredEvent;
import com.jobradar.tracker.job.JobIngestService;
import com.jobradar.tracker.job.JobIngestService.Outcome;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ApiIntegrationTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JobIngestService ingest;

    // ---- helpers -------------------------------------------------------------

    private String register() throws Exception {
        String email = "student-" + UUID.randomUUID() + "@uni.edu";
        var body = Map.of("email", email, "displayName", "Student", "password", "correct-horse");
        JsonNode res = read(mvc.perform(post("/api/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(body))).andExpect(status().isCreated()));
        return res.get("token").asText();
    }

    private ResultActions call(MockHttpServletRequestBuilder req, String token, Object body) throws Exception {
        req.header("Authorization", "Bearer " + token);
        if (body != null) req.contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body));
        return mvc.perform(req);
    }

    private JsonNode read(ResultActions r) throws Exception {
        return json.readTree(r.andReturn().getResponse().getContentAsString());
    }

    private JobDiscoveredEvent event(String externalId, String title) {
        return new JobDiscoveredEvent(UUID.randomUUID().toString(), "job.discovered", "greenhouse", "Acme",
                externalId, title, "Chicago, IL", "https://acme.com/jobs/" + externalId,
                OffsetDateTime.parse("2026-11-01T09:00:00-05:00"), OffsetDateTime.now());
    }

    // ---- auth ----------------------------------------------------------------

    @Test
    void registerLoginAndRejectBadCredentials() throws Exception {
        String email = "login-" + UUID.randomUUID() + "@uni.edu";
        var reg = Map.of("email", email, "displayName", "Ada", "password", "correct-horse");
        mvc.perform(post("/api/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(reg))).andExpect(status().isCreated());
        mvc.perform(post("/api/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(reg))).andExpect(status().isConflict());

        String token = read(mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("email", email.toUpperCase(), "password", "correct-horse"))))
                .andExpect(status().isOk())).get("token").asText();
        call(get("/api/auth/me"), token, null).andExpect(jsonPath("$.displayName").value("Ada"));

        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("email", email, "password", "wrong-password"))))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void validationErrorsAreProblemDetails() throws Exception {
        mvc.perform(post("/api/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"not-an-email\",\"displayName\":\"x\",\"password\":\"short\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    @Test
    void protectedEndpointsRequireToken() throws Exception {
        mvc.perform(get("/api/applications")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/jobs").header("Authorization", "Bearer not.a.jwt")).andExpect(status().isUnauthorized());
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    // ---- ingestion -----------------------------------------------------------

    @Test
    void ingestionIsIdempotent() {
        var e = event("idem-" + UUID.randomUUID(), "SWE Intern");
        assertThat(ingest.ingest(e)).isEqualTo(Outcome.CREATED);
        assertThat(ingest.ingest(e)).isEqualTo(Outcome.DUPLICATE);
        // Redelivery with a different eventId is still the same posting.
        assertThat(ingest.ingest(new JobDiscoveredEvent("other-id", e.eventType(), e.source(), e.company(),
                e.externalId(), e.title(), e.location(), e.url(), e.postedAt(), e.discoveredAt())))
                .isEqualTo(Outcome.DUPLICATE);
    }

    // ---- jobs feed + kanban --------------------------------------------------

    @Test
    void trackScrapedJobAndDragAcrossBoard() throws Exception {
        String token = register();
        String ext = "kanban-" + UUID.randomUUID();
        ingest.ingest(event(ext, "Backend Engineer Intern " + ext));

        JsonNode feed = read(call(get("/api/jobs").param("q", ext), token, null).andExpect(status().isOk()));
        assertThat(feed.get("totalItems").asInt()).isEqualTo(1);
        long jobId = feed.get("items").get(0).get("id").asLong();
        assertThat(feed.get("items").get(0).get("tracked").asBoolean()).isFalse();

        // Track the scraped job, then add two manual applications.
        JsonNode tracked = read(call(post("/api/applications"), token, Map.of("jobId", jobId))
                .andExpect(status().isCreated()));
        assertThat(tracked.get("company").asText()).isEqualTo("Acme");
        assertThat(tracked.get("status").asText()).isEqualTo("SAVED");
        call(post("/api/applications"), token, Map.of("jobId", jobId)).andExpect(status().isConflict());

        long manualA = read(call(post("/api/applications"), token,
                Map.of("company", "Visa", "roleTitle", "SWE Intern", "status", "APPLIED"))).get("id").asLong();
        long manualB = read(call(post("/api/applications"), token,
                Map.of("company", "Uline", "roleTitle", "IT Intern", "status", "APPLIED"))).get("id").asLong();
        call(post("/api/applications"), token, Map.of("company", "NoTitle")).andExpect(status().isBadRequest());

        assertThat(read(call(get("/api/jobs").param("q", ext), token, null))
                .get("items").get(0).get("tracked").asBoolean()).isTrue();

        // Drag the saved card to the top of APPLIED: it should get appliedAt and push the others down.
        long trackedId = tracked.get("id").asLong();
        JsonNode moved = read(call(put("/api/applications/" + trackedId + "/move"), token,
                Map.of("status", "APPLIED", "position", 0)).andExpect(status().isOk()));
        assertThat(moved.get("appliedAt").isNull()).isFalse();

        JsonNode board = read(call(get("/api/applications"), token, null));
        assertThat(positionsOf(board, "APPLIED")).containsExactly(trackedId, manualA, manualB);

        // Reorder within a column, then delete: positions stay dense.
        call(put("/api/applications/" + manualB + "/move"), token, Map.of("status", "APPLIED", "position", 0))
                .andExpect(status().isOk());
        assertThat(positionsOf(read(call(get("/api/applications"), token, null)), "APPLIED"))
                .containsExactly(manualB, trackedId, manualA);
        call(delete("/api/applications/" + trackedId), token, null).andExpect(status().isNoContent());
        JsonNode after = read(call(get("/api/applications"), token, null));
        assertThat(positionsOf(after, "APPLIED")).containsExactly(manualB, manualA);
        after.forEach(a -> assertThat(a.get("position").asInt()).isLessThan(2));

        call(patch("/api/applications/" + manualA), token, Map.of("notes", "OA due Friday"))
                .andExpect(jsonPath("$.notes").value("OA due Friday"));

        call(get("/api/applications/stats"), token, null)
                .andExpect(jsonPath("$.total").value(2))
                .andExpect(jsonPath("$.applied").value(2))
                .andExpect(jsonPath("$.byStatus.APPLIED").value(2))
                .andExpect(jsonPath("$.byStatus.OFFER").value(0));
    }

    @Test
    void usersCannotSeeOrModifyEachOthersCards() throws Exception {
        String alice = register();
        String mallory = register();
        long id = read(call(post("/api/applications"), alice,
                Map.of("company", "Wellmark", "roleTitle", "Data Intern"))).get("id").asLong();

        assertThat(read(call(get("/api/applications"), mallory, null)).size()).isZero();
        call(patch("/api/applications/" + id), mallory, Map.of("notes", "hacked")).andExpect(status().isNotFound());
        call(put("/api/applications/" + id + "/move"), mallory, Map.of("status", "OFFER", "position", 0))
                .andExpect(status().isNotFound());
        call(delete("/api/applications/" + id), mallory, null).andExpect(status().isNotFound());
        assertThat(read(call(get("/api/applications"), alice, null)).size()).isEqualTo(1);
    }

    private static java.util.List<Long> positionsOf(JsonNode board, String status) {
        var cards = new java.util.ArrayList<JsonNode>();
        board.forEach(a -> { if (a.get("status").asText().equals(status)) cards.add(a); });
        cards.sort(java.util.Comparator.comparingInt(a -> a.get("position").asInt()));
        return cards.stream().map(a -> a.get("id").asLong()).toList();
    }
}
