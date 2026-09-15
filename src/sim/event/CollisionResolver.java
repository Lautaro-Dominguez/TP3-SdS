package sim.event;

import sim.core.Obstacle;
import sim.core.Particle;

/** Applies post-collision velocities (and the fresh-to-used transition) for each event type. */
public final class CollisionResolver {

    private CollisionResolver() {}

    public static void resolveWallX(Particle p) {
        p.setVelocity(-p.getVx(), p.getVy());
    }

    public static void resolveWallY(Particle p) {
        p.setVelocity(p.getVx(), -p.getVy());
    }

    /** Whether this wall-x contact counts as a goal: particle still fresh and within the arc. */
    public static boolean isGoal(Particle p, double w, double d) {
        if (p.getState() != Particle.State.FRESH) {
            return false;
        }
        double y = p.getPosition().y;
        return Math.abs(y - w / 2) <= d / 2;
    }

    /** Elastic collision between two moving particles of arbitrary mass (impulse formulas). */
    public static void resolveParticlePair(Particle a, Particle b) {
        double dx = b.getPosition().x - a.getPosition().x;
        double dy = b.getPosition().y - a.getPosition().y;
        double dvx = b.getVx() - a.getVx();
        double dvy = b.getVy() - a.getVy();
        double sigma = a.getRadius() + b.getRadius();
        double mi = a.getMass();
        double mj = b.getMass();

        double dvdr = dvx * dx + dvy * dy;
        double j = 2 * mi * mj * dvdr / (sigma * (mi + mj));
        double jx = j * dx / sigma;
        double jy = j * dy / sigma;

        a.setVelocity(a.getVx() + jx / mi, a.getVy() + jy / mi);
        b.setVelocity(b.getVx() - jx / mj, b.getVy() - jy / mj);
    }

    /**
     * Elastic collision of a moving particle against a fixed, infinite-mass obstacle: specular
     * reflection about the contact normal. This is the mj -> infinity limit of the general
     * impulse formula above (equivalently, the cn=ct=1 case of the fixed-obstacle collision
     * operator), simplified to v' = v - 2(v . n^)n^.
     */
    public static void resolveObstacle(Particle p, Obstacle o) {
        double nx = p.getPosition().x - o.getPosition().x;
        double ny = p.getPosition().y - o.getPosition().y;
        double norm = Math.sqrt(nx * nx + ny * ny);
        nx /= norm;
        ny /= norm;

        double vdotn = p.getVx() * nx + p.getVy() * ny;
        p.setVelocity(p.getVx() - 2 * vdotn * nx, p.getVy() - 2 * vdotn * ny);
    }
}
