package com.jobradar.tracker.application;

/** Kanban columns, in board order. */
public enum ApplicationStatus {
    SAVED,
    APPLIED,
    ONLINE_ASSESSMENT,
    INTERVIEWING,
    OFFER,
    REJECTED;

    public boolean countsAsApplied() {
        return this != SAVED;
    }
}
