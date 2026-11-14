package com.jobradar.tracker.auth;

import com.jobradar.tracker.common.CurrentUser;
import com.jobradar.tracker.config.JwtProperties;
import com.jobradar.tracker.user.AppUser;
import com.jobradar.tracker.user.UserRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    public record RegisterRequest(
            @NotBlank @Email @Size(max = 255) String email,
            @NotBlank @Size(max = 100) String displayName,
            @NotBlank @Size(min = 8, max = 72, message = "password must be 8-72 characters") String password) {}

    public record LoginRequest(@NotBlank String email, @NotBlank String password) {}

    public record UserResponse(Long id, String email, String displayName) {
        static UserResponse from(AppUser u) {
            return new UserResponse(u.getId(), u.getEmail(), u.getDisplayName());
        }
    }

    public record AuthResponse(String token, Instant expiresAt, UserResponse user) {}

    private final UserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final JwtEncoder jwtEncoder;
    private final JwtProperties jwtProps;

    public AuthController(UserRepository users, PasswordEncoder passwordEncoder, JwtEncoder jwtEncoder,
                          JwtProperties jwtProps) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.jwtEncoder = jwtEncoder;
        this.jwtProps = jwtProps;
    }

    @PostMapping("/register")
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    @Operation(summary = "Create an account and receive a JWT")
    public AuthResponse register(@Valid @RequestBody RegisterRequest req) {
        String email = req.email().trim().toLowerCase();
        if (users.existsByEmailIgnoreCase(email)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "an account with this email already exists");
        }
        AppUser user = users.save(new AppUser(email, req.displayName().trim(), passwordEncoder.encode(req.password())));
        return issue(user);
    }

    @PostMapping("/login")
    @Transactional(readOnly = true)
    @Operation(summary = "Exchange credentials for a JWT")
    public AuthResponse login(@Valid @RequestBody LoginRequest req) {
        AppUser user = users.findByEmailIgnoreCase(req.email().trim())
                .filter(u -> passwordEncoder.matches(req.password(), u.getPasswordHash()))
                // Same message for unknown email and wrong password: no account enumeration.
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "invalid email or password"));
        return issue(user);
    }

    @GetMapping("/me")
    @SecurityRequirement(name = "bearer")
    @Transactional(readOnly = true)
    public UserResponse me(@AuthenticationPrincipal Jwt jwt) {
        return users.findById(CurrentUser.id(jwt))
                .map(UserResponse::from)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "user no longer exists"));
    }

    private AuthResponse issue(AppUser user) {
        Instant now = Instant.now();
        Instant expiresAt = now.plus(jwtProps.ttl());
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer("jobradar-tracker")
                .subject(user.getId().toString())
                .issuedAt(now)
                .expiresAt(expiresAt)
                .claim("email", user.getEmail())
                .claim("name", user.getDisplayName())
                .build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(
                JwsHeader.with(MacAlgorithm.HS256).build(), claims)).getTokenValue();
        return new AuthResponse(token, expiresAt, UserResponse.from(user));
    }
}
