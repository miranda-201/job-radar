package com.jobradar.tracker.job;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Arrays;
import java.util.Locale;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/** Keys used to recognize the same posting arriving from different sources. */
public final class Dedup {

    private static final Pattern TRACKING_PARAM =
            Pattern.compile("(?i)^(utm_.*|ref|referrer|source|src|gh_src|lever-source.*|lever-origin)$");
    private static final Pattern NON_ALNUM = Pattern.compile("[^\\p{L}\\p{N}]+");

    private Dedup() {}

    /** Lower-cased scheme/host, no fragment, no tracking params, no trailing slash. */
    public static String canonicalUrl(String url) {
        if (url == null || url.isBlank()) return null;
        try {
            URI u = new URI(url.trim());
            String query = u.getRawQuery() == null ? null : Arrays.stream(u.getRawQuery().split("&"))
                    .filter(p -> !p.isEmpty() && !TRACKING_PARAM.matcher(p.split("=", 2)[0]).matches())
                    .collect(Collectors.joining("&"));
            String path = u.getRawPath() == null ? "" : u.getRawPath().replaceAll("/+$", "");
            String host = u.getHost() == null ? "" : u.getHost().toLowerCase(Locale.ROOT);
            String scheme = u.getScheme() == null ? "https" : u.getScheme().toLowerCase(Locale.ROOT);
            String port = u.getPort() == -1 ? "" : ":" + u.getPort();
            return scheme + "://" + host + port + path + (query == null || query.isEmpty() ? "" : "?" + query);
        } catch (URISyntaxException e) {
            return url.trim();
        }
    }

    /** "Stripe", "Software Engineer Intern (Summer 2027)" -> "stripe|software engineer intern summer 2027" */
    public static String fingerprint(String company, String title) {
        return normalize(company) + "|" + normalize(title);
    }

    private static String normalize(String s) {
        return s == null ? "" : NON_ALNUM.matcher(s.toLowerCase(Locale.ROOT)).replaceAll(" ").trim();
    }
}
