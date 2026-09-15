package sim.event;

import sim.core.Particle;

/**
 * A candidate collision, timestamped at the absolute simulation time it would occur. Carries the
 * stamp(s) of every particle involved, recorded when the event was computed, so a stale event
 * (one of the involved particles has since collided with something else and changed velocity)
 * can be recognized and discarded when popped from the queue instead of having to be located and
 * removed from the heap at the moment it goes stale.
 */
public final class Event implements Comparable<Event> {

    public enum Type { WALL_X, WALL_Y, PARTICLE_PARTICLE, PARTICLE_OBSTACLE }

    public final double time;
    public final Type type;
    public final int i;
    public final int j;              // other particle index, only for PARTICLE_PARTICLE; -1 otherwise
    public final int obstacleIndex;   // only for PARTICLE_OBSTACLE; -1 otherwise
    private final int stampI;
    private final int stampJ;        // only meaningful when j >= 0

    private Event(double time, Type type, int i, int j, int obstacleIndex, int stampI, int stampJ) {
        this.time = time;
        this.type = type;
        this.i = i;
        this.j = j;
        this.obstacleIndex = obstacleIndex;
        this.stampI = stampI;
        this.stampJ = stampJ;
    }

    public static Event wallX(double time, int i, int stampI) {
        return new Event(time, Type.WALL_X, i, -1, -1, stampI, -1);
    }

    public static Event wallY(double time, int i, int stampI) {
        return new Event(time, Type.WALL_Y, i, -1, -1, stampI, -1);
    }

    public static Event particlePair(double time, int i, int j, int stampI, int stampJ) {
        return new Event(time, Type.PARTICLE_PARTICLE, i, j, -1, stampI, stampJ);
    }

    public static Event particleObstacle(double time, int i, int obstacleIndex, int stampI) {
        return new Event(time, Type.PARTICLE_OBSTACLE, i, -1, obstacleIndex, stampI, -1);
    }

    /** True if no involved particle has collided (and thus changed velocity) since this was computed. */
    public boolean isValid(Particle[] particles) {
        if (particles[i].getStamp() != stampI) {
            return false;
        }
        return j < 0 || particles[j].getStamp() == stampJ;
    }

    @Override
    public int compareTo(Event other) {
        return Double.compare(this.time, other.time);
    }
}
