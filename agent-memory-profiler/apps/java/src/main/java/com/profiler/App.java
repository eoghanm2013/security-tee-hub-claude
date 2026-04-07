package com.profiler;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

@SpringBootApplication
@RestController
public class App {

    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

    @GetMapping("/")
    public Map<String, String> health() {
        return Map.of("status", "ok", "tracer", "java");
    }

    @GetMapping("/search")
    public Map<String, Object> search(@RequestParam(defaultValue = "") String q) {
        List<String> results = IntStream.range(0, 5)
                .mapToObj(i -> "result-" + i)
                .toList();
        return Map.of("query", q, "results", results);
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestParam(defaultValue = "") String username) {
        return Map.of("authenticated", false, "user", username);
    }
}
