package sim.event;

import sim.core.Particle;

import java.util.PriorityQueue;

/**
 * Thin wrapper around a time-ordered heap of candidate {@link Event}s, with lazy invalidation:
 * {@link #pollNextValid} discards stale events (see {@link Event#isValid}) as it pops them,
 * instead of the caller ever needing to remove a specific event from the middle of the heap.
 */
public final class EventQueue {

    private final PriorityQueue<Event> heap = new PriorityQueue<>();

    public void offer(Event event) {
        heap.offer(event);
    }

    /** Pops and returns the earliest still-valid event, or null if none remain. */
    public Event pollNextValid(Particle[] particles) {
        Event e;
        while ((e = heap.poll()) != null) {
            if (e.isValid(particles)) {
                return e;
            }
        }
        return null;
    }
}
