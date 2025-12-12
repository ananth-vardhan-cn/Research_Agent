const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function App() {
  return (
    <div className="container">
      <h1>Propaganda Extension</h1>
      <p>Popup UI is running.</p>
      <p>
        Backend API base URL: <code>{apiBaseUrl}</code>
      </p>
    </div>
  );
}
