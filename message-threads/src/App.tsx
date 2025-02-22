import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ThreadVisualization from "./components/ThreadVisualization";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-white">
        <header className="bg-gray-100 shadow">
          <div className="max-w-7xl mx-auto py-4 px-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Message Threads
            </h1>
          </div>
        </header>
        <main className="w-full overflow-x-auto">
          <ThreadVisualization />
        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
