package sim.event;

import sim.core.Obstacle;
import sim.core.Particle;

/**
 * Time-to-collision formulas. Every method returns a duration relative to "now" (the particle's
 * own current, already-advanced position) - callers add the current global simulation clock to
 * get an absolute event time. Infinity means "will never happen from this state".
 */
public final class CollisionTime {

    private CollisionTime() {}

    /** Time until the particle's border reaches the x=0 or x=L wall, whichever it's heading to. */
    public static double wallX(Particle p, double l) {
        double vx = p.getVx();
        double x = p.getPosition().x;
        double r = p.getRadius();
        if (vx > 0) return (l - r - x) / vx;
        if (vx < 0) return (r - x) / vx;
        return Double.POSITIVE_INFINITY;
    }

    /** Time until the particle's border reaches the y=0 or y=W wall, whichever it's heading to. */
    public static double wallY(Particle p, double w) {
        double vy = p.getVy();
        double y = p.getPosition().y;
        double r = p.getRadius();
        if (vy > 0) return (w - r - y) / vy;
        if (vy < 0) return (r - y) / vy;
        return Double.POSITIVE_INFINITY;
    }

    public static double particlePair(Particle a, Particle b) {
        double dx = b.getPosition().x - a.getPosition().x;
        double dy = b.getPosition().y - a.getPosition().y;
        double dvx = b.getVx() - a.getVx();
        double dvy = b.getVy() - a.getVy();
        double sigma = a.getRadius() + b.getRadius();
        return timeFromRelative(dx, dy, dvx, dvy, sigma);
    }

    /** Same two-body formula, with the obstacle treated as a fixed (zero-velocity) circle. */
    public static double particleObstacle(Particle p, Obstacle o) {
        double dx = o.getPosition().x - p.getPosition().x;
        double dy = o.getPosition().y - p.getPosition().y;
        double dvx = -p.getVx();
        double dvy = -p.getVy();
        double sigma = p.getRadius() + o.getRadius();
        return timeFromRelative(dx, dy, dvx, dvy, sigma);
    }

    private static double timeFromRelative(double dx, double dy, double dvx, double dvy, double sigma) {
        double dvdr = dvx * dx + dvy * dy;
        if (dvdr >= 0) return Double.POSITIVE_INFINITY;
        double dvdv = dvx * dvx + dvy * dvy;
        double drdr = dx * dx + dy * dy;
        double d = dvdr * dvdr - dvdv * (drdr - sigma * sigma);
        if (d < 0) return Double.POSITIVE_INFINITY;
        return -(dvdr + Math.sqrt(d)) / dvdv;
    }
}
