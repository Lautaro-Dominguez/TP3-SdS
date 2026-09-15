package sim.core;

/**
 * A moving disk: mutable position/velocity (event-driven MD advances them in place between
 * events instead of rebuilding particles every step) plus a one-way FRESH -> USED state.
 *
 * {@code stamp} is bumped every time this particle's velocity changes (wall/particle/obstacle
 * collision). The event queue records each candidate event's stamp at creation time and treats a
 * popped event as stale - and discards it - if the stamp no longer matches, which is the usual
 * lazy-invalidation trick for event-driven MD: no per-collision heap surgery is needed.
 */
public final class Particle {

    public enum State { FRESH, USED }

    private final int id;
    private final double radius;
    private final double mass;

    private Vector2D position;
    private double vx;
    private double vy;
    private State state;
    private int stamp;

    public Particle(int id, Vector2D position, double vx, double vy, double radius, double mass) {
        this.id = id;
        this.position = position;
        this.vx = vx;
        this.vy = vy;
        this.radius = radius;
        this.mass = mass;
        this.state = State.FRESH;
        this.stamp = 0;
    }

    public int getId() { return id; }

    public double getRadius() { return radius; }

    public double getMass() { return mass; }

    public Vector2D getPosition() { return position; }

    public double getVx() { return vx; }

    public double getVy() { return vy; }

    public double speed() { return Math.sqrt(vx * vx + vy * vy); }

    public double angle() {
        double a = Math.atan2(vy, vx);
        return a < 0 ? a + 2 * Math.PI : a;
    }

    public State getState() { return state; }

    public int getStamp() { return stamp; }

    /** Advances the position by MRU over duration dt; velocity is unaffected. */
    public void advance(double dt) {
        position = new Vector2D(position.x + vx * dt, position.y + vy * dt);
    }

    /** Sets a new velocity after a collision and invalidates any event computed before this. */
    public void setVelocity(double vx, double vy) {
        this.vx = vx;
        this.vy = vy;
        this.stamp++;
    }

    /** First contact with the goal segment: FRESH -> USED. No-op if already USED. */
    public void markUsed() {
        this.state = State.USED;
    }
}
