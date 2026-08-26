const REPO_URL = "https://github.com/triptitamanna221-wq/Free-Case-Law-Search-for-Indian-Courts";

export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto max-w-6xl px-4 py-6 text-center text-sm text-muted-foreground sm:px-6">
        <p>
          Powered by FastAPI + PostgreSQL + pgvector.{" "}
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="underline underline-offset-4">
            View source
          </a>
        </p>
      </div>
    </footer>
  );
}
