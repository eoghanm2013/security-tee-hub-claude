const express = require("express");
const app = express();
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.get("/", (req, res) => {
  res.json({ status: "ok", tracer: "node" });
});

app.get("/search", (req, res) => {
  const q = req.query.q || "";
  res.json({ query: q, results: Array.from({ length: 5 }, (_, i) => `result-${i}`) });
});

app.post("/login", (req, res) => {
  const username = req.body.username || "";
  res.json({ authenticated: false, user: username });
});

app.listen(8080, "0.0.0.0", () => {
  console.log("Node profiler app listening on :8080");
});
