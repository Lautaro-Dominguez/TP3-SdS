package sim.generation;

import sim.core.Obstacle;
import sim.core.Particle;
import sim.core.Vector2D;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Places N non-overlapping circular particles of a fixed radius inside a [0,L] x [0,W]
 * rectangle, avoiding both each other and a set of fixed obstacles, via rejection sampling
 * ("random sequential addition"): propose a random center, accept it only if it doesn't overlap
 * anything placed so far. A SpatialHashGrid keeps each check local instead of O(N) per attempt.
 *
 * Purely a rejection method: as requested density approaches close packing, acceptance
 * probability collapses and no finite attempt budget reliably succeeds - maxAttemptsPerParticle
 * just turns "would loop forever" into a clear, catchable failure.
 */
public final class ParticlePlacer {

    private static final int DEFAULT_MAX_ATTEMPTS = 50_000;

    private ParticlePlacer() {}

    public static List<Particle> place(double l, double w, int n, double radius, double mass,
                                        double v0, List<Obstacle> obstacles, Random rng) {
        return place(l, w, n, radius, mass, v0, obstacles, rng, DEFAULT_MAX_ATTEMPTS);
    }

    public static List<Particle> place(double l, double w, int n, double radius, double mass,
                                        double v0, List<Obstacle> obstacles, Random rng,
                                        int maxAttemptsPerParticle) {
        if (n <= 0) throw new IllegalArgumentException("N must be positive");
        if (radius <= 0) throw new IllegalArgumentException("radius must be positive");
        if (l <= 2 * radius || w <= 2 * radius) {
            throw new IllegalArgumentException(String.format(
                "a particle of radius %.6f does not fit inside a %.6f x %.6f domain", radius, l, w));
        }

        validateObstacles(l, w, obstacles);

        double maxObstacleRadius = 0;
        for (Obstacle o : obstacles) {
            maxObstacleRadius = Math.max(maxObstacleRadius, o.getRadius());
        }
        double cellSize = Math.max(2 * radius, radius + maxObstacleRadius);
        SpatialHashGrid grid = new SpatialHashGrid(l, w, cellSize);
        for (Obstacle o : obstacles) {
            grid.insert(o.getPosition().x, o.getPosition().y, o.getRadius());
        }

        List<Particle> placed = new ArrayList<>(n);
        for (int id = 0; id < n; id++) {
            double x = Double.NaN, y = Double.NaN;
            boolean found = false;
            for (int attempt = 0; attempt < maxAttemptsPerParticle; attempt++) {
                double cx = radius + rng.nextDouble() * (l - 2 * radius);
                double cy = radius + rng.nextDouble() * (w - 2 * radius);
                if (!grid.overlaps(cx, cy, radius)) {
                    x = cx;
                    y = cy;
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw new IllegalStateException(
                    "Could not place particle " + id + " of " + n + " after " + maxAttemptsPerParticle
                    + " attempts. The requested density is probably too high for this L/W/r/obstacle "
                    + "configuration - try a lower N, a larger table, or fewer/smaller obstacles.");
            }

            double theta = rng.nextDouble() * 2 * Math.PI;
            double vx = v0 * Math.cos(theta);
            double vy = v0 * Math.sin(theta);
            placed.add(new Particle(id, new Vector2D(x, y), vx, vy, radius, mass));
            grid.insert(x, y, radius);
        }
        return placed;
    }

    /** Obstacles are an external input; only warn (don't abort) if they look inconsistent. */
    private static void validateObstacles(double l, double w, List<Obstacle> obstacles) {
        for (Obstacle o : obstacles) {
            double x = o.getPosition().x;
            double y = o.getPosition().y;
            double r = o.getRadius();
            if (x - r < 0 || x + r > l || y - r < 0 || y + r > w) {
                System.err.printf(
                    "WARNING: obstacle %d (x=%.6f y=%.6f R=%.6f) pokes outside the %.6f x %.6f domain%n",
                    o.getId(), x, y, r, l, w);
            }
        }
        for (int i = 0; i < obstacles.size(); i++) {
            for (int j = i + 1; j < obstacles.size(); j++) {
                Obstacle a = obstacles.get(i);
                Obstacle b = obstacles.get(j);
                double dist = a.getPosition().distanceTo(b.getPosition());
                if (dist < a.getRadius() + b.getRadius()) {
                    System.err.printf("WARNING: obstacles %d and %d overlap each other%n", a.getId(), b.getId());
                }
            }
        }
    }
}
