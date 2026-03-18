const http = require("http");

const port = 3000;

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tree Counting SaaS</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f6f7fb; }
    main { max-width: 880px; margin: 40px auto; padding: 0 20px; }
    .card { background: #fff; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.08); padding: 20px; }
    code { color: #0b7285; }
  </style>
</head>
<body>
  <main>
    <div class="card">
      <h1>Tree Counting SaaS</h1>
      <p>Frontend fallback server is running (Next.js scaffold also exists in this folder).</p>
      <p>Step 1 runtime verification mode.</p>
    </div>
  </main>
</body>
</html>`;

http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", service: "frontend-fallback" }));
    return;
  }
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(html);
}).listen(port, "127.0.0.1", () => {
  console.log(`frontend fallback listening on http://127.0.0.1:${port}`);
});
