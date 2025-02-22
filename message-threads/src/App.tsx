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
      <div className="w-screen h-screen bg-white overflow-hidden">
        <ThreadVisualization />
      </div>
    </QueryClientProvider>
  );
}

export default App;
