FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src src
RUN mvn package -DskipTests -B

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN wget -O dd-java-agent.jar https://dtdg.co/latest-java-tracer
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
CMD ["java", "-javaagent:dd-java-agent.jar", "-jar", "app.jar"]
