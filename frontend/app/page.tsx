export default async function HomePage() {
  let apiStatus = "unreachable";
  try {
    const res = await fetch(process.env.API_BASE_URL ? `${process.env.API_BASE_URL}/health` : "http://localhost:8000/health", {
      cache: "no-store"
    });
    apiStatus = res.ok ? "healthy" : `error (${res.status})`;
  } catch {
    apiStatus = "unreachable";
  }

  return (
    <main>
      <div className="card">
        <h1>Tree Counting SaaS</h1>
        <p>Step 1 scaffold is running.</p>
        <p>API health: <code>{apiStatus}</code></p>
      </div>
    </main>
  );
}
