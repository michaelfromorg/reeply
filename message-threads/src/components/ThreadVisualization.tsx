import React, { useRef, useMemo, useEffect, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { getThreads, Thread } from "../lib/api";

const THREAD_LIMIT = 50;
const DAY_CELL_WIDTH = 20; // width in pixels per day
const ONE_DAY = 24 * 60 * 60 * 1000;

type DateIndicatorProps = {
  minDate: Date;
  DAY_CELL_WIDTH: number;
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
};

const DateIndicator: React.FC<DateIndicatorProps> = ({
  minDate,
  DAY_CELL_WIDTH,
  scrollContainerRef,
}) => {
  const [visibleRange, setVisibleRange] = useState({
    start: minDate,
    end: minDate,
  });

  useEffect(() => {
    const scrollEl = scrollContainerRef.current;
    if (!scrollEl) return;
    const onScroll = () => {
      const { scrollLeft, clientWidth } = scrollEl;
      const startIndex = Math.floor(scrollLeft / DAY_CELL_WIDTH);
      const endIndex = Math.floor((scrollLeft + clientWidth) / DAY_CELL_WIDTH);
      const startDate = new Date(minDate.getTime() + startIndex * ONE_DAY);
      const endDate = new Date(minDate.getTime() + endIndex * ONE_DAY);
      setVisibleRange({ start: startDate, end: endDate });
    };
    scrollEl.addEventListener("scroll", onScroll);
    onScroll();
    return () => scrollEl.removeEventListener("scroll", onScroll);
  }, [minDate, DAY_CELL_WIDTH, scrollContainerRef]);

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        background: "#f7f7f7",
        padding: "0.5rem",
        borderBottom: "1px solid #ddd",
        zIndex: 3,
        height: "50px",
        display: "flex",
        alignItems: "center",
      }}
    >
      <strong>Showing:</strong> {visibleRange.start.toISOString().split("T")[0]}{" "}
      — {visibleRange.end.toISOString().split("T")[0]}
    </div>
  );
};

const ThreadVisualization: React.FC = () => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Infinite query to load threads
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

  const threads: Thread[] = useMemo(() => data?.pages.flat() || [], [data]);

  // Determine overall timeline range using threads’ first/last message dates
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

  const daysCount = useMemo(() => {
    return Math.ceil((maxDate.getTime() - minDate.getTime()) / ONE_DAY) + 1;
  }, [minDate, maxDate]);

  // Virtualizer for rows (vertical scrolling)
  const rowVirtualizer = useVirtualizer({
    count: threads.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 60,
    overscan: 5,
  });

  // Create a single, shared horizontal virtualizer for timeline columns
  const horizontalVirtualizer = useVirtualizer({
    horizontal: true,
    count: daysCount,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => DAY_CELL_WIDTH,
    overscan: 5,
  });

  // Fetch next page when scrolling near the bottom of the vertical list
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

  // Helper: group a thread’s messages by day
  const getMessageCountByDay = (thread: Thread): Record<string, number> => {
    const counts: Record<string, number> = {};
    thread.messages.forEach((msg) => {
      const day = new Date(msg.date).toISOString().split("T")[0];
      counts[day] = (counts[day] || 0) + 1;
    });
    return counts;
  };

  return (
    <div style={{ width: "100vw", height: "100vh", overflow: "hidden" }}>
      <DateIndicator
        minDate={minDate}
        DAY_CELL_WIDTH={DAY_CELL_WIDTH}
        scrollContainerRef={scrollContainerRef}
      />
      <div
        ref={scrollContainerRef}
        id="thread-scroll-container"
        style={{
          height: "calc(100vh - 65px)",
          overflow: "auto",
          position: "relative",
        }}
      >
        <div
          style={{
            height: rowVirtualizer.getTotalSize(),
            width: 220 + horizontalVirtualizer.getTotalSize(), // total timeline width
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
                  width: 220 + horizontalVirtualizer.getTotalSize(),
                  transform: `translateY(${virtualRow.start}px)`,
                  display: "flex",
                  alignItems: "center",
                  height: virtualRow.size,
                  borderBottom: "1px solid #ddd",
                }}
              >
                <div
                  style={{
                    width: 200,
                    padding: "0 10px",
                    flexShrink: 0,
                    position: "sticky",
                    left: 0,
                    background: "white",
                    zIndex: 2,
                  }}
                >
                  {thread.address}
                </div>
                <div
                  style={{
                    flex: 1,
                    position: "relative",
                    height: "100%",
                  }}
                >
                  {/* Use the shared horizontal virtualizer for this row */}
                  <div
                    style={{
                      position: "relative",
                      height: "100%",
                      width: horizontalVirtualizer.getTotalSize(),
                      willChange: "transform",
                    }}
                  >
                    {horizontalVirtualizer
                      .getVirtualItems()
                      .map((virtualColumn) => {
                        const dayIndex = virtualColumn.index;
                        const currentDate = new Date(
                          minDate.getTime() + dayIndex * ONE_DAY
                        );
                        const dateKey = currentDate.toISOString().split("T")[0];
                        const count = messageCounts[dateKey] || 0;
                        return (
                          <div
                            key={dateKey}
                            style={{
                              position: "absolute",
                              left: virtualColumn.start,
                              top: 0,
                              width: DAY_CELL_WIDTH,
                              height: "100%",
                            }}
                          >
                            {count > 0 && (
                              <div
                                style={{
                                  width: Math.min(12, count * 3),
                                  height: Math.min(12, count * 3),
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
