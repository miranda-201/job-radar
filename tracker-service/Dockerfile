# syntax=docker/dockerfile:1

# ---- build -------------------------------------------------------------------------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 mvn -B -q dependency:go-offline
COPY src src
RUN --mount=type=cache,target=/root/.m2 mvn -B -q package -DskipTests -Djacoco.skip=true \
 && java -Djarmode=tools -jar target/tracker-service.jar extract --destination /out

# ---- runtime: JRE only, non-root ----------------------------------------------------
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S -G app -u 10001 app
# Extracted layout (app jar + lib/) starts faster than the fat jar and caches better.
COPY --from=build /out/lib ./lib
COPY --from=build /out/tracker-service.jar ./tracker-service.jar
USER app
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError"
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
  CMD wget -qO- http://localhost:8080/actuator/health/readiness | grep -q '"UP"' || exit 1
ENTRYPOINT ["java", "-jar", "tracker-service.jar"]
