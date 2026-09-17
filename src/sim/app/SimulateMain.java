package sim.app;

import sim.core.Obstacle;
import sim.core.Particle;
import sim.event.CollisionResolver;
import sim.event.CollisionTime;
import sim.event.Event;
import sim.event.EventQueue;
import sim.io.GoalFileIO;
import sim.io.ObstacleFileIO;
import sim.io.PropertiesFileIO;
import sim.io.StateFileIO;

import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Event-driven molecular dynamics engine for the billar-metegol table: repeatedly advances every
 * particle by uniform rectilinear motion (MRU) to the next collision (wall / particle-particle /
 * particle-obstacle), resolves that collision, and appends a new block to the trajectory file
 * every {@code saveEvery} accepted events - until every particle has become "usada" or the
 * simulation clock reaches {@code tmax}.
 *
 * Every goal is logged (time + accumulated goal count), and t90 - the time at which
 * Fu = N_g/N reaches 0.9 - is reported on stdout, so a sweep driver can read it without ever
 * touching the trajectory file.
 *
 * Usage:
 *   java -cp out sim.app.SimulateMain [--L 1.20] [--W 0.68] [--d 0.20]
 *       [--in output/particles.txt] [--props output/properties.txt] [--obstacles obstacles.txt]
 *       [--tmax 100] [--saveEvery 1] [--out output/particles.txt] [--goals output/goals.txt]
 */
public final class SimulateMain {

    public static void main(String[] args) {
        Map<String, String> flags = parseFlags(args);

        double l = Double.parseDouble(flags.getOrDefault("L", "1.20"));
        double w = Double.parseDouble(flags.getOrDefault("W", "0.68"));
        double d = Double.parseDouble(flags.getOrDefault("d", "0.20"));
        double tmax = Double.parseDouble(flags.getOrDefault("tmax", "Infinity"));
        int saveEvery = Integer.parseInt(flags.getOrDefault("saveEvery", "1"));
        Path in = Path.of(flags.getOrDefault("in", "output/particles.txt"));
        Path props = Path.of(flags.getOrDefault("props", "output/properties.txt"));
        Path out = Path.of(flags.getOrDefault("out", flags.getOrDefault("in", "output/particles.txt")));
        String goalsFlag = flags.get("goals");

        // saveEvery 0 disables trajectory output entirely: the configuration sweeps of point 1.2
        // only need the goal log, and writing one N-particle block per event would dominate both
        // the runtime and the disk usage of a few hundred runs.
        boolean writeTrajectory = saveEvery > 0;

        List<Obstacle> obstacles = Collections.emptyList();
        String obstaclesFlag = flags.get("obstacles");
        if (obstaclesFlag != null) {
            obstacles = ObstacleFileIO.read(Path.of(obstaclesFlag));
        }

        PropertiesFileIO.Properties properties = PropertiesFileIO.read(props);
        List<Particle> particleList = StateFileIO.readFirstBlock(in, properties.radii, properties.masses);
        Particle[] particles = particleList.toArray(new Particle[0]);
        int n = particles.length;

        if (writeTrajectory && !out.equals(in)) {
            StateFileIO.writeInitial(out, particleList);
        }

        EventQueue queue = new EventQueue();
        for (int i = 0; i < n; i++) {
            enqueueWallAndObstacleEvents(queue, particles, obstacles, l, w, 0.0, i);
            for (int j = i + 1; j < n; j++) {
                enqueuePairEvent(queue, particles, 0.0, i, j);
            }
        }

        double tGlobal = 0.0;
        double lastSavedTime = 0.0;
        int eventsSinceSave = 0;
        long eventsProcessed = 0;
        int usedCount = 0;
        for (Particle p : particles) {
            if (p.getState() == Particle.State.USED) usedCount++;
        }

        // At most one goal per particle (a used particle never scores again), so N entries is an
        // exact bound on the goal log.
        double[] goalTimes = new double[n];
        int[] goalCounts = new int[n];
        int goalsLogged = 0;
        int goalsForT90 = goalsForT90(n);
        double t90 = usedCount >= goalsForT90 ? 0.0 : Double.NaN;

        while (true) {
            Event e = queue.pollNextValid(particles);
            double nextTime = (e == null) ? Double.POSITIVE_INFINITY : e.time;

            if (nextTime > tmax) {
                advanceAll(particles, tmax - tGlobal);
                tGlobal = tmax;
                break;
            }
            if (e == null) {
                break; // closed elastic box: shouldn't happen, but nothing left to do either way
            }

            advanceAll(particles, e.time - tGlobal);
            tGlobal = e.time;
            eventsProcessed++;

            switch (e.type) {
                case WALL_X -> {
                    Particle p = particles[e.i];
                    if (CollisionResolver.isGoal(p, w, d)) {
                        p.markUsed();
                        usedCount++;
                        goalTimes[goalsLogged] = tGlobal;
                        goalCounts[goalsLogged] = usedCount;
                        goalsLogged++;
                        if (Double.isNaN(t90) && usedCount >= goalsForT90) {
                            t90 = tGlobal;
                        }
                    }
                    CollisionResolver.resolveWallX(p);
                    enqueueWallAndObstacleEvents(queue, particles, obstacles, l, w, tGlobal, e.i);
                    for (int j = 0; j < n; j++) {
                        if (j != e.i) enqueuePairEvent(queue, particles, tGlobal, e.i, j);
                    }
                }
                case WALL_Y -> {
                    Particle p = particles[e.i];
                    CollisionResolver.resolveWallY(p);
                    enqueueWallAndObstacleEvents(queue, particles, obstacles, l, w, tGlobal, e.i);
                    for (int j = 0; j < n; j++) {
                        if (j != e.i) enqueuePairEvent(queue, particles, tGlobal, e.i, j);
                    }
                }
                case PARTICLE_PARTICLE -> {
                    CollisionResolver.resolveParticlePair(particles[e.i], particles[e.j]);
                    for (int k : new int[] { e.i, e.j }) {
                        enqueueWallAndObstacleEvents(queue, particles, obstacles, l, w, tGlobal, k);
                        for (int j = 0; j < n; j++) {
                            if (j != k) enqueuePairEvent(queue, particles, tGlobal, k, j);
                        }
                    }
                }
                case PARTICLE_OBSTACLE -> {
                    CollisionResolver.resolveObstacle(particles[e.i], obstacles.get(e.obstacleIndex));
                    enqueueWallAndObstacleEvents(queue, particles, obstacles, l, w, tGlobal, e.i);
                    for (int j = 0; j < n; j++) {
                        if (j != e.i) enqueuePairEvent(queue, particles, tGlobal, e.i, j);
                    }
                }
            }

            if (writeTrajectory) {
                eventsSinceSave++;
                if (eventsSinceSave >= saveEvery) {
                    StateFileIO.appendBlock(out, tGlobal, particleList);
                    lastSavedTime = tGlobal;
                    eventsSinceSave = 0;
                }
            }

            if (usedCount >= n) {
                break;
            }
        }

        if (writeTrajectory && tGlobal > lastSavedTime) {
            StateFileIO.appendBlock(out, tGlobal, particleList);
        }
        if (goalsFlag != null) {
            GoalFileIO.write(Path.of(goalsFlag), goalTimes, goalCounts, goalsLogged);
        }

        System.out.printf(
            "Simulated %d events (N=%d, t=%.6f, used=%d/%d, obstacles=%d) -> %s%n",
            eventsProcessed, n, tGlobal, usedCount, n,
            obstacles.size(), writeTrajectory ? out.toString() : "(no trajectory)");
        // Machine-readable summary line for the sweep drivers: t90 is NaN when Fu never reached
        // 0.9 within tmax (the "censored" case the competition ranks by goals instead).
        System.out.printf(Locale.US, "t90 %.6f ng %d%n", t90, usedCount);
    }

    /**
     * Smallest goal count k with k/N >= 0.9, i.e. k = ceil(9N/10), in exact integer arithmetic.
     * Math.ceil(0.9 * n) happens to agree for every n we care about, but it relies on 0.9 * n
     * rounding favourably (0.9 is not representable in binary); this form is exact by
     * construction. For N=100 both give 90.
     */
    private static int goalsForT90(int n) {
        return (9 * n + 9) / 10;
    }

    private static void advanceAll(Particle[] particles, double dt) {
        if (dt <= 0) return;
        for (Particle p : particles) {
            p.advance(dt);
        }
    }

    private static void enqueueWallAndObstacleEvents(EventQueue queue, Particle[] particles,
                                                       List<Obstacle> obstacles, double l, double w,
                                                       double tGlobal, int i) {
        Particle p = particles[i];
        double twx = CollisionTime.wallX(p, l);
        if (Double.isFinite(twx)) {
            queue.offer(Event.wallX(tGlobal + twx, i, p.getStamp()));
        }
        double twy = CollisionTime.wallY(p, w);
        if (Double.isFinite(twy)) {
            queue.offer(Event.wallY(tGlobal + twy, i, p.getStamp()));
        }
        for (int k = 0; k < obstacles.size(); k++) {
            double t = CollisionTime.particleObstacle(p, obstacles.get(k));
            if (Double.isFinite(t)) {
                queue.offer(Event.particleObstacle(tGlobal + t, i, k, p.getStamp()));
            }
        }
    }

    private static void enqueuePairEvent(EventQueue queue, Particle[] particles, double tGlobal, int i, int j) {
        double t = CollisionTime.particlePair(particles[i], particles[j]);
        if (Double.isFinite(t)) {
            int a = Math.min(i, j);
            int b = Math.max(i, j);
            queue.offer(Event.particlePair(tGlobal + t, a, b, particles[a].getStamp(), particles[b].getStamp()));
        }
    }

    private static Map<String, String> parseFlags(String[] args) {
        Map<String, String> raw = new HashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) {
            String key = args[i].startsWith("--") ? args[i].substring(2) : args[i];
            raw.put(key, args[i + 1]);
        }
        return raw;
    }
}
