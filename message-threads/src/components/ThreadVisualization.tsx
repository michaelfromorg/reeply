import React, { useRef, useMemo, useEffect } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { getThreads, Thread } from "../lib/api";

const THREAD_LIMIT = 50;
const DAY_CELL_WIDTH = 20; // width in pixels per day

const ThreadVisualization: React.FC = () => {
  // A ref for the scrollable container (vertical list of threads)
  const parentRef = useRef<HTMLDivElement>(null);

  // Use an infinite query to load threads from the server
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery<Thread[]>({
      initialPageParam: 0,
      queryKey: ["threads"],
      queryFn: ({ pageParam = 0 }: any) => getThreads(pageParam, THREAD_LIMIT),
      getNextPageParam: (lastPage, allPages) =>
        lastPage.length < THREAD_LIMIT
          ? undefined
          : allPages.length * THREAD_LIMIT,
    });

  // Flatten the paginated threads into one array
  const threads: Thread[] = useMemo(() => {
    return data?.pages.flat() || [];
  }, [data]);

  // Compute the overall timeline range based on thread boundaries.
  // We use each thread’s first and last message dates.
  const { minDate, maxDate } = useMemo(() => {
    if (threads.length === 0) {
      const now = new Date();
      return { minDate: now, maxDate: now };
    }
    let minTime = Infinity;
    let maxTime = -Infinity;
    threads.forEach((thread) => {
      const first = new Date(thread.first_message).getTime();
      const last = new Date(thread.last_message).getTime();
      if (first < minTime) minTime = first;
      if (last > maxTime) maxTime = last;
    });
    return { minDate: new Date(minTime), maxDate: new Date(maxTime) };
  }, [threads]);

  // Compute the total number of days for the timeline.
  const oneDay = 24 * 60 * 60 * 1000;
  const daysCount = useMemo(() => {
    return Math.ceil((maxDate.getTime() - minDate.getTime()) / oneDay) + 1;
  }, [minDate, maxDate]);

  // Set up row virtualization for the threads list
  const rowVirtualizer = useVirtualizer({
    count: threads.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60, // estimated row height (adjust as needed)
    overscan: 5,
  });

  // When scrolling near the bottom, fetch the next page of threads
  useEffect(() => {
    const virtualItems = rowVirtualizer.getVirtualItems();
    if (virtualItems.length === 0) return;
    const lastItem = virtualItems[virtualItems.length - 1];
    if (
      lastItem.index >= threads.length - 1 &&
      hasNextPage &&
      !isFetchingNextPage
    ) {
      fetchNextPage();
    }
  }, [
    rowVirtualizer.getVirtualItems(),
    threads.length,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  ]);

  // Helper to group messages by day (formatted as "YYYY-MM-DD")
  const getMessageCountByDay = (thread: Thread): Record<string, number> => {
    const counts: Record<string, number> = {};
    thread.messages.forEach((msg) => {
      const day = new Date(msg.date).toISOString().split("T")[0];
      counts[day] = (counts[day] || 0) + 1;
    });
    return counts;
  };

  return (
    <div style={{ padding: "1rem" }}>
      {/* Vertical scroll container for the threads */}
      <div ref={parentRef} className="h-full overflow-auto">
        <div
          style={{
            height: rowVirtualizer.getTotalSize(),
            width: "100%",
            position: "relative",
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const thread = threads[virtualRow.index];
            const messageCounts = getMessageCountByDay(thread);
            return (
              <div
                key={thread.address}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: 220 + daysCount * DAY_CELL_WIDTH,
                  transform: `translateY(${virtualRow.start}px)`,
                  display: "flex",
                  alignItems: "center",
                  height: virtualRow.size,
                  borderBottom: "1px solid #ddd",
                }}
              >
                {/* Display the thread address on the left */}
                <div style={{ width: 200, padding: "0 10px", flexShrink: 0 }}>
                  {thread.address}
                </div>
                {/* Timeline container for the conversation */}
                <div
                  style={{
                    flex: 1,
                    position: "relative",
                    height: "100%",
                  }}
                >
                  <div
                    style={{
                      position: "relative",
                      minWidth: daysCount * DAY_CELL_WIDTH,
                      height: "100%",
                      willChange: "transform",
                    }}
                  >
                    {Array.from({ length: daysCount }).map((_, dayIndex) => {
                      const currentDate = new Date(
                        minDate.getTime() + dayIndex * oneDay
                      );
                      const dateKey = currentDate.toISOString().split("T")[0];
                      const count = messageCounts[dateKey] || 0;
                      return (
                        <div
                          key={dateKey}
                          style={{
                            position: "absolute",
                            left: dayIndex * DAY_CELL_WIDTH,
                            top: 0,
                            width: DAY_CELL_WIDTH,
                            height: "100%",
                          }}
                        >
                          {count > 0 && (
                            <div
                              style={{
                                width: Math.min(12, count * 5), // dot size roughly proportional to message count
                                height: Math.min(12, count * 5),
                                borderRadius: "50%",
                                backgroundColor: "blue",
                                position: "absolute",
                                top: "50%",
                                left: "50%",
                                transform: "translate(-50%, -50%)",
                              }}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {isFetchingNextPage && (
        <div style={{ textAlign: "center", padding: "1rem" }}>
          Loading more threads...
        </div>
      )}
    </div>
  );
};

export default ThreadVisualization;
